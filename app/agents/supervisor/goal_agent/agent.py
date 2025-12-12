from __future__ import annotations

import datetime
import logging
from typing import Optional

from langchain_cerebras import ChatCerebras
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from app.core.config import config
from app.observability.logging_config import configure_logging
from app.services.llm.prompt_loader import prompt_loader

from .subgraph import create_goal_subgraph
from .tools import (
    create_goal,
    create_history_record,
    delete_goal,
    delete_history_record,
    get_goal_by_id,
    get_goal_history,
    get_in_progress_goal,
    switch_goal_status,
    update_goal,
    update_history_record,
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
        logger.info("Initializing GoalAgent with Cerebras models")

        # Use provided callbacks or initialize from env vars
        if callbacks is not None:
            self.callbacks = callbacks
            logger.info("[Langfuse][goal] Using %d external callback(s) from supervisor", len(callbacks))
        else:
            goal_pk = config.LANGFUSE_PUBLIC_GOAL_KEY
            goal_sk = config.LANGFUSE_SECRET_GOAL_KEY
            goal_host = config.LANGFUSE_HOST
            self.callbacks = []
            if goal_pk and goal_sk and goal_host:
                try:
                    _goal_client = Langfuse(  # noqa: F841
                        public_key=goal_pk,
                        secret_key=goal_sk,
                        host=goal_host
                    )
                    self.callbacks = [CallbackHandler(public_key=goal_pk)]
                    logger.info("[Langfuse][goal] Callback handler initialized from env vars")
                except Exception as e:
                    logger.warning("[Langfuse][goal] Failed to init callback handler: %s: %s", type(e).__name__, e)
                    self.callbacks = []
            else:
                logger.warning(
                    "[Langfuse][goal] Env vars missing or incomplete; tracing disabled (host=%s)",
                    goal_host,
                )
        self.llm = ChatCerebras(
            model="gpt-oss-120b",
            api_key=config.CEREBRAS_API_KEY,
            temperature=config.GOAL_AGENT_TEMPERATURE or 0.4,
            callbacks=self.callbacks,
        )

    def _create_agent_with_tools(self):
        from .tools_math import calculate

        tools = [
            create_goal, update_goal, get_in_progress_goal,
            delete_goal, switch_goal_status, get_goal_by_id,
            get_goal_history, create_history_record, update_history_record, delete_history_record,
            calculate
        ]

        def prompt_builder(user_id: str = None):
            return self._create_system_prompt(user_id)

        return create_goal_subgraph(self.llm, tools, prompt_builder, self.callbacks)

    async def _create_system_prompt(self, user_id: str = None) -> str:

        base_prompt = prompt_loader.load("goal_agent_system_prompt")
        today = datetime.datetime.now().strftime("%B %d, %Y")
        base_prompt = f"TODAY: {today}\n\n{base_prompt}"

        # Inject user's goals into context
        if user_id:
            from .utils import get_goals_for_user
            try:
                user_goals_response = await get_goals_for_user(user_id)
                if user_goals_response and user_goals_response.get('goals'):
                    import json

                    goals_context = "\n\n## USER'S CURRENT GOALS (RAW)\n\n"
                    goals_context += json.dumps(user_goals_response, ensure_ascii=False, indent=2)
                    return base_prompt + goals_context
            except Exception as e:
                logger.warning(f"Failed to inject goals context: {e}")

        return base_prompt

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


def get_goal_agent(callbacks: list | None = None) -> GoalAgent:
    """Get goal agent instance, allowing optional callback refresh."""
    global _goal_agent
    if _goal_agent is None or callbacks is not None:
        _goal_agent = GoalAgent(callbacks=callbacks)
    return _goal_agent
