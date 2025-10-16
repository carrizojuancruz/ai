from __future__ import annotations

import logging
from typing import Optional

from langchain_aws import ChatBedrockConverse
from langfuse.callback import CallbackHandler
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from app.core.config import config
from app.observability.logging_config import configure_logging

from .subgraph import create_goal_subgraph
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


class GoalAgent:
    """Goal agent for financial goals management and coaching."""

    def __init__(self, callbacks: list = None):
        """Initialize GoalAgent with optional external callbacks.

        Args:
            callbacks: Optional list of callbacks (e.g., from supervisor). If None, will try to
                      initialize Langfuse callbacks from environment variables.

        """
        configure_logging()
        logger.info("Initializing GoalAgent with Bedrock models")

        # Use provided callbacks or initialize from env vars
        if callbacks is not None:
            self.callbacks = callbacks
            logger.info("[Langfuse][goal] Using %d external callback(s) from supervisor", len(callbacks))
        else:
            goal_pk = config.LANGFUSE_PUBLIC_GOAL_KEY
            goal_sk = config.LANGFUSE_SECRET_GOAL_KEY
            goal_host = config.LANGFUSE_HOST_GOAL
            self.callbacks = []
            if goal_pk and goal_sk and goal_host:
                try:
                    self.callbacks = [CallbackHandler(public_key=goal_pk, secret_key=goal_sk, host=goal_host)]
                    logger.info("[Langfuse][goal] Callback handler initialized from env vars")
                except Exception as e:
                    logger.warning("[Langfuse][goal] Failed to init callback handler: %s: %s", type(e).__name__, e)
                    self.callbacks = []
            else:
                logger.warning(
                    "[Langfuse][goal] Env vars missing or incomplete; tracing disabled (host=%s)",
                    goal_host,
                )
        self.llm = ChatBedrockConverse(
            model_id=config.GOAL_AGENT_MODEL_ID,
            region_name=config.GOAL_AGENT_MODEL_REGION,
            provider=config.GOAL_AGENT_PROVIDER,
            temperature=config.GOAL_AGENT_TEMPERATURE,
            callbacks=self.callbacks,
        )

    def _create_agent_with_tools(self):
        from .tools_math import calculate

        tools = [
            create_goal, update_goal, get_in_progress_goal,
            list_goals, delete_goal, switch_goal_status, get_goal_by_id,
            calculate
        ]

        def prompt_builder():
            return self._create_system_prompt()

        return create_goal_subgraph(self.llm, tools, prompt_builder, self.callbacks)

    def _create_system_prompt(self) -> str:
        from app.services.llm.prompt_loader import prompt_loader
        return prompt_loader.load("goal_agent_system_prompt")

    async def process_query_with_agent(self, query: str, user_id) -> Command:
        agent = self._create_agent_with_tools()
        messages = [{"role": "user", "content": query}]

        # Include callbacks in config for proper Langfuse tracing
        run_config = {
            "recursion_limit": 10,
            "callbacks": self.callbacks,
            "configurable": {"user_id": user_id}
        }

        logger.info("[Langfuse][goal] Invoking agent with callbacks enabled: %s", bool(self.callbacks))
        agent_command = await agent.ainvoke({"messages": messages}, config=run_config)
        return agent_command


# Convenience function to maintain backward compatibility
def compile_goal_agent_graph() -> CompiledStateGraph:
    """Compile the goal agent graph for financial goals management."""
    agent = GoalAgent()
    return agent._create_agent_with_tools()


# Global singleton instance for backward compatibility
_goal_agent: Optional[GoalAgent] = None


def get_goal_agent() -> GoalAgent:
    """Get goal agent instance."""
    global _goal_agent
    if _goal_agent is None:
        _goal_agent = GoalAgent()
    return _goal_agent
