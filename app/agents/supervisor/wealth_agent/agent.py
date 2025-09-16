from __future__ import annotations

import logging

from langchain_aws import ChatBedrock
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from app.core.config import config
from app.observability.logging_config import configure_logging

from .prompts import WEALTH_AGENT_PROMPT
from .tools import search_kb

logger = logging.getLogger(__name__)


def compile_wealth_agent_graph() -> CompiledStateGraph:
    """Compile the wealth agent graph."""
    configure_logging()

    region = config.AWS_REGION
    model_id = config.BEDROCK_MODEL_ID
    guardrail_id = config.BEDROCK_GUARDRAIL_ID
    guardrail_version = str(config.BEDROCK_GUARDRAIL_VERSION)

    guardrails = {
        "guardrailIdentifier": guardrail_id,
        "guardrailVersion": guardrail_version,
        "trace": True,
    }
    logger.info(f"[WEALTH_AGENT] Guardrails: {guardrails}")

    chat_bedrock = ChatBedrock(model_id=model_id, region_name=region, guardrails=guardrails)

    wealth_agent = create_react_agent(
        model=chat_bedrock,
        tools=[search_kb],
        prompt=WEALTH_AGENT_PROMPT,
        name="wealth_agent",
    )

    builder = StateGraph(MessagesState)

    builder.add_node(wealth_agent)
    builder.add_edge(START, "wealth_agent")
    builder.add_edge("wealth_agent", END)

    return builder.compile()
