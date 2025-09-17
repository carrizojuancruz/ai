from __future__ import annotations

import logging

from langchain_aws import ChatBedrockConverse
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from app.observability.logging_config import configure_logging  # ensure logging format

from .prompts import GOAL_AGENT_PROMPT
from .tools import (
    create_goal,
    delete_goal,
    get_goal_by_id,
    get_in_progress_goal,
    list_goals,
    switch_goal_status,
    update_goal,
)

logger = logging.getLogger(__name__)


def compile_goal_agent_graph() -> CompiledStateGraph:
    """Compile the goal agent graph for financial goals management."""
    configure_logging()

    guardrails = {
        "guardrailIdentifier": "arn:aws:bedrock:us-west-2:905418355862:guardrail/nqa94s84lt6u",
        "guardrailVersion": "DRAFT",
        "trace": "enabled",
    }

    chat_bedrock = ChatBedrockConverse(
        model_id="openai.gpt-oss-120b-1:0",
        region_name="us-west-2",
        temperature=0.4,
        guardrail_config=guardrails,
    )
    # checkpointer = MemorySaver()
    goal_agent = create_react_agent(
        model=chat_bedrock,
        tools=[
            create_goal, update_goal, get_in_progress_goal,
            list_goals, delete_goal, switch_goal_status, get_goal_by_id
        ],
        prompt=GOAL_AGENT_PROMPT,
        name="goal_agent",
    )

    builder = StateGraph(MessagesState)

    # Add the agent node
    builder.add_node("goal_agent", goal_agent)

    # Define the flow
    builder.add_edge(START, "goal_agent")
    builder.add_edge("goal_agent", END)

    return builder.compile()
