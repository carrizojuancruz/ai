from __future__ import annotations

import logging
import os

from langchain_aws import ChatBedrock
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from .handoff import create_task_description_handoff_tool
from .prompts import SUPERVISOR_PROMPT
from .workers import math_agent, research_agent
from .tools import knowledge_search_tool

logger = logging.getLogger(__name__)

def compile_supervisor_graph() -> CompiledStateGraph:
    assign_to_research_agent_with_description = create_task_description_handoff_tool(
        agent_name="research_agent", description="Assign task to a researcher agent."
    )
    assign_to_math_agent_with_description = create_task_description_handoff_tool(
        agent_name="math_agent", description="Assign task to a math agent."
    )

    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
    guardrail_id = os.getenv("BEDROCK_GUARDRAIL_ID")
    guardrail_version = os.getenv("BEDROCK_GUARDRAIL_VERSION")

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
    builder.add_node(
        supervisor_agent_with_description, destinations=("research_agent", "math_agent", END)
    )
    builder.add_node("research_agent", research_agent)
    builder.add_node("math_agent", math_agent)
    builder.add_edge(START, "supervisor")
    builder.add_edge("research_agent", "supervisor")
    builder.add_edge("math_agent", "supervisor")
    return builder.compile()


