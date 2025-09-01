from __future__ import annotations

import logging

from langchain_aws import ChatBedrock
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from app.agents.supervisor.memory import episodic_capture, memory_context, memory_hotpath
from app.core.config import config
from app.services.memory.store_factory import create_s3_vectors_store_from_env

from .handoff import create_task_description_handoff_tool
from .prompts import SUPERVISOR_PROMPT
from .tools import knowledge_search_tool
from .workers import math_agent, research_agent

logger = logging.getLogger(__name__)

def compile_supervisor_graph() -> CompiledStateGraph:
    assign_to_research_agent_with_description = create_task_description_handoff_tool(
        agent_name="research_agent", description="Assign task to a researcher agent."
    )
    assign_to_math_agent_with_description = create_task_description_handoff_tool(
        agent_name="math_agent", description="Assign task to a math agent."
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

    supervisor_agent_with_description = create_react_agent(
        model=chat_bedrock,
        tools=[
            assign_to_research_agent_with_description,
            assign_to_math_agent_with_description,
            knowledge_search_tool,
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
        supervisor_agent_with_description, destinations=("research_agent", "math_agent", "episodic_capture")
    )

    # --- Specialist agent nodes ---
    builder.add_node("episodic_capture", episodic_capture)
    builder.add_node("research_agent", research_agent)
    builder.add_node("math_agent", math_agent)

    # --- Define edges between nodes ---
    builder.add_edge(START, "memory_hotpath")
    builder.add_edge("memory_hotpath", "memory_context")
    builder.add_edge("memory_context", "supervisor")
    builder.add_edge("research_agent", "supervisor")
    builder.add_edge("math_agent", "supervisor")
    builder.add_edge("supervisor", "episodic_capture")
    builder.add_edge("episodic_capture", END)

    # --- Store configuration for tools ---
    store = create_s3_vectors_store_from_env()
    return builder.compile(store=store)


