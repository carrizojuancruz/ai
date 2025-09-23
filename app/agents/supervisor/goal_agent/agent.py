from __future__ import annotations

import logging
import threading
from typing import Optional

from langchain_aws import ChatBedrock
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from app.core.config import config
from app.observability.logging_config import configure_logging

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


class GoalAgentSingleton:
    """Singleton class for the goal agent graph compilation."""

    _instance: Optional['GoalAgentSingleton'] = None
    _lock = threading.Lock()
    _compiled_graph: Optional[CompiledStateGraph] = None

    def __new__(cls) -> 'GoalAgentSingleton':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def get_compiled_graph(self) -> CompiledStateGraph:
        """Get the compiled goal agent graph, creating it if necessary."""
        if self._compiled_graph is None:
            with self._lock:
                if self._compiled_graph is None:
                    self._compiled_graph = self._compile_goal_agent_graph()
        return self._compiled_graph

    def _compile_goal_agent_graph(self) -> CompiledStateGraph:
        """Compile the goal agent graph for financial goals management."""
        configure_logging()

        region = config.GOAL_AGENT_MODEL_REGION
        model_id = config.GOAL_AGENT_MODEL_ID
        guardrail_id = config.BEDROCK_GUARDRAIL_ID
        guardrail_version = str(config.BEDROCK_GUARDRAIL_VERSION)

        guardrails = {
            "guardrailIdentifier": guardrail_id,
            "guardrailVersion": guardrail_version,
            "trace": True,
        }

        logger.info(f"[GOAL_AGENT] Guardrails: {guardrails}")
        logger.info(f"[GOAL_AGENT] MODELS: {model_id} in {region}, DEFAULT: {config.BEDROCK_MODEL_ID}")
        chat_bedrock = ChatBedrock(model_id=model_id, region_name=region, guardrails=guardrails)
        checkpointer = MemorySaver()

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

        # Main goal agent node
        builder.add_node("goal_agent", goal_agent)

        # Define the flow
        builder.add_edge(START, "goal_agent")
        builder.add_edge("goal_agent", END)

        return builder.compile(checkpointer=checkpointer)


# Convenience function to maintain backward compatibility
def compile_goal_agent_graph() -> CompiledStateGraph:
    """Compile the goal agent graph for financial goals management."""
    return GoalAgentSingleton().get_compiled_graph()


# Global singleton instance
goal_agent_singleton = GoalAgentSingleton()
