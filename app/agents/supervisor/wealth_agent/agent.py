from __future__ import annotations

import logging

from langchain_aws import ChatBedrockConverse
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from app.observability.logging_config import configure_logging

from .prompts import WEALTH_AGENT_PROMPT
from .tools import search_kb

logger = logging.getLogger(__name__)


def compile_wealth_agent_graph() -> CompiledStateGraph:
    """Compile the wealth agent graph."""
    configure_logging()

    guardrails = {
        "guardrailIdentifier": "arn:aws:bedrock:us-west-2:905418355862:guardrail/nqa94s84lt6u",
        "guardrailVersion": "DRAFT",
        "trace": "enabled",
    }

    logger.info(f"[WEALTH_AGENT] Guardrails: {guardrails}")

    chat_bedrock = ChatBedrockConverse(
        model_id="openai.gpt-oss-120b-1:0", region_name="us-west-2", temperature=0.2, guardrail_config=guardrails
    )

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
