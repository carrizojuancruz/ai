from __future__ import annotations

import logging

from langchain_aws import ChatBedrock
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from app.agents.supervisor.memory import episodic_capture, memory_context, memory_hotpath
from app.core.config import config
from app.services.memory.store_factory import create_s3_vectors_store_from_env

from .finance_agent.agent import finance_agent
from .handoff import create_task_description_handoff_tool
from .prompts import SUPERVISOR_PROMPT
from .workers import goal_agent, wealth_agent
from .finance_agent.agent import finance_agent

logger = logging.getLogger(__name__)

def compile_supervisor_graph() -> CompiledStateGraph:
    assign_to_finance_agent_with_description = create_task_description_handoff_tool(
        agent_name="finance_agent", description="Assign task to a finance agent for account and transaction queries."
    )
    assign_to_goal_agent_with_description = create_task_description_handoff_tool(
        agent_name="goal_agent", description="Assign task to the goal agent for financial objectives."
    )
    assign_to_wealth_agent_with_description = create_task_description_handoff_tool(
        agent_name="wealth_agent", description="Assign task to a wealth agent."
    )

    region = config.AWS_REGION
    model_id = config.BEDROCK_MODEL_ID
    guardrail_id = config.BEDROCK_GUARDRAIL_ID
    guardrail_version = str(config.BEDROCK_GUARDRAIL_VERSION)

    guardrails = {
        "guardrailIdentifier": guardrail_id,
        "guardrailVersion": guardrail_version,
        "trace": True,
    }
    logger.info(f"Guardrails: {guardrails}")
    chat_bedrock = ChatBedrock(model_id=model_id, region_name=region, guardrails=guardrails)
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
    builder.add_node("memory_hotpath", memory_hotpath)
    builder.add_node("memory_context", memory_context)

    # --- Main supervisor node and destinations ---
    builder.add_node(
        supervisor_agent_with_description, destinations=("finance_agent", "wealth_agent", "goal_agent", "episodic_capture")
    )


    # --- Specialist agent nodes ---
    builder.add_node("episodic_capture", episodic_capture)
    builder.add_node("finance_agent", finance_agent)
    builder.add_node("wealth_agent", wealth_agent)
    builder.add_node("goal_agent", goal_agent)

    # --- Define edges between nodes ---
    builder.add_edge(START, "memory_hotpath")
    builder.add_edge("memory_hotpath", "memory_context")
    builder.add_edge("memory_context", "supervisor")
    builder.add_edge("finance_agent", "supervisor")
    builder.add_edge("wealth_agent", "supervisor")
    builder.add_edge("goal_agent", "supervisor")
    builder.add_edge("supervisor", "episodic_capture")
    builder.add_edge("episodic_capture", END)
    store = create_s3_vectors_store_from_env()
    checkpointer = MemorySaver()
    return builder.compile(store=store, checkpointer=checkpointer)


