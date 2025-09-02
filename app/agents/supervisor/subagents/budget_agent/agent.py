from __future__ import annotations

import logging

from langchain_aws import ChatBedrock
from langgraph.graph import START, END, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from app.core.config import config
from app.observability.logging_config import configure_logging  # ensure logging format

from app.agents.supervisor.subagents.budget_agent.prompts import BUDGET_AGENT_PROMPT
from app.agents.supervisor.subagents.budget_agent.tools import create_budget, update_budget, get_active_budget, delete_budget


logger = logging.getLogger(__name__)


def compile_budget_agent_graph() -> CompiledStateGraph:
    """
    Compile the budget agent graph.
    """
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
    logger.info(f"[BUDGET_AGENT] Guardrails: {guardrails}")

    chat_bedrock = ChatBedrock(model_id=model_id, region_name=region, guardrails=guardrails)

    budget_agent = create_react_agent(
        model=chat_bedrock,
        tools=[create_budget, update_budget, get_active_budget, delete_budget],
        prompt=BUDGET_AGENT_PROMPT,
        name="budget_agent",
    )

    builder = StateGraph(MessagesState)

    builder.add_node(budget_agent)
    builder.add_edge(START, "budget_agent")
    builder.add_edge("budget_agent", END)

    return builder.compile()
