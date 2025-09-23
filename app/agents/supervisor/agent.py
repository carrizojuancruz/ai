from __future__ import annotations

import logging

from langchain_aws import ChatBedrockConverse
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent
from langchain_core.messages.utils import count_tokens_approximately
from langmem.short_term import RunningSummary, SummarizationNode

from app.agents.supervisor.memory import episodic_capture, memory_context, memory_hotpath
from app.core.config import config
from app.services.memory.store_factory import create_s3_vectors_store_from_env

from .handoff import create_task_description_handoff_tool
from .prompts import SUPERVISOR_PROMPT
from .workers import finance_router, goal_agent, wealth_agent

logger = logging.getLogger(__name__)


def compile_supervisor_graph() -> CompiledStateGraph:
    assign_to_finance_agent_with_description = create_task_description_handoff_tool(
        agent_name="finance_agent",
        description="Assign task to a finance agent for account and transaction queries.",
        destination_agent_name="finance_router",
        tool_name="transfer_to_finance_agent",
    )
    assign_to_goal_agent_with_description = create_task_description_handoff_tool(
        agent_name="goal_agent", description="Assign task to the goal agent for financial objectives."
    )
    assign_to_wealth_agent_with_description = create_task_description_handoff_tool(
        agent_name="wealth_agent",
        description="Assign task to a wealth agent for financial assistance and education: government benefits (SNAP, LIHEAP, housing assistance), consumer protection, credit/debt management, student loans, budgeting tools, emergency funds, tax credits, state-specific financial programs, crisis resources, scam prevention, and general financial literacy."
    )

    guardrails = {
        "guardrailIdentifier": config.SUPERVISOR_AGENT_GUARDRAIL_ID,
        "guardrailVersion": config.SUPERVISOR_AGENT_GUARDRAIL_VERSION,
        "trace": "enabled",
    }

    chat_bedrock = ChatBedrockConverse(
        model_id=config.SUPERVISOR_AGENT_MODEL_ID,
        region_name=config.SUPERVISOR_AGENT_MODEL_REGION,
        temperature=config.SUPERVISOR_AGENT_TEMPERATURE,
        guardrail_config=guardrails
    )
    checkpointer = MemorySaver()

    if config.SUMMARY_MODEL_ID:
        summarize_model = ChatBedrockConverse(
            model_id=config.SUMMARY_MODEL_ID,
            region_name=config.SUPERVISOR_AGENT_MODEL_REGION,
            temperature=0.0,
        )
    else:
        summarize_model = chat_bedrock

    supervisor_agent_with_description = create_react_agent(
        model=chat_bedrock,
        tools=[
            assign_to_finance_agent_with_description,
            assign_to_wealth_agent_with_description,
            assign_to_goal_agent_with_description,
        ],
        prompt=SUPERVISOR_PROMPT,
        name="supervisor",
    )

    class SupervisorState(MessagesState):
        context: dict[str, RunningSummary]

    builder = StateGraph(SupervisorState)

    summarization_node = SummarizationNode(
        token_counter=count_tokens_approximately,
        model=summarize_model,
        max_tokens=int(config.SUMMARY_MAX_TOKENS),
        max_tokens_before_summary=int(config.SUMMARY_MAX_TOKENS_BEFORE),
        max_summary_tokens=int(config.SUMMARY_MAX_SUMMARY_TOKENS),
        output_messages_key="messages",
    )

    # --- Memory and context nodes ---
    builder.add_node("summarize", summarization_node)
    builder.add_node("memory_hotpath", memory_hotpath)
    builder.add_node("memory_context", memory_context)

    # --- Main supervisor node and destinations ---
    builder.add_node(
        supervisor_agent_with_description,
        destinations=("finance_agent", "wealth_agent", "goal_agent", "episodic_capture"),
    )

    # --- Specialist agent nodes ---
    builder.add_node("episodic_capture", episodic_capture)
    builder.add_node("finance_router", finance_router)
    from .finance_agent.agent import finance_agent as finance_worker

    builder.add_node("finance_agent", finance_worker)
    builder.add_node("wealth_agent", wealth_agent)
    builder.add_node("goal_agent", goal_agent)

    # --- Define edges between nodes ---
    builder.add_edge(START, "summarize")
    builder.add_edge("summarize", "memory_hotpath")
    builder.add_edge("memory_hotpath", "memory_context")
    builder.add_edge("memory_context", "supervisor")
    builder.add_edge("finance_router", "supervisor")
    builder.add_edge("finance_agent", "supervisor")
    builder.add_edge("wealth_agent", "supervisor")
    builder.add_edge("goal_agent", "supervisor")
    builder.add_edge("supervisor", "episodic_capture")
    builder.add_edge("episodic_capture", END)
    store = create_s3_vectors_store_from_env()
    checkpointer = MemorySaver()
    return builder.compile(store=store, checkpointer=checkpointer)
