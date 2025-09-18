from __future__ import annotations

import logging

from langchain_aws import ChatBedrockConverse
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from app.agents.supervisor.memory import episodic_capture, icebreaker_consumer, memory_context, memory_hotpath
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
        description="Assign task to a wealth agent for personal finance education: credit building, budgeting, debt management, emergency funds, financial literacy, government programs, consumer protection, and money management guidance.",
    )

    str(config.BEDROCK_GUARDRAIL_VERSION)

    guardrails = {
        "guardrailIdentifier": "arn:aws:bedrock:us-west-2:905418355862:guardrail/nqa94s84lt6u",
        "guardrailVersion": "DRAFT",
        "trace": "enabled",
    }

    chat_bedrock = ChatBedrockConverse(
        model_id="openai.gpt-oss-120b-1:0",
        region_name="us-west-2",
        temperature=0.4,
        guardrail_config=guardrails
    )
    checkpointer = MemorySaver()

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

    builder = StateGraph(MessagesState)

    # --- Memory and context nodes ---
    builder.add_node("icebreaker_consumer", icebreaker_consumer)
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
    builder.add_edge(START, "icebreaker_consumer")
    builder.add_edge("icebreaker_consumer", "memory_hotpath")
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
