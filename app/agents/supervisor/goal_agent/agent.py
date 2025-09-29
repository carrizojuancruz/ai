from __future__ import annotations

import logging
from typing import Optional

from langchain_aws import ChatBedrockConverse
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from app.core.config import config
from app.observability.logging_config import configure_logging

from .prompts import GOAL_AGENT_PROMPT
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

    def __init__(self):
        configure_logging()
        logger.info("Initializing GoalAgent with Bedrock models")

        self.llm = ChatBedrockConverse(
            model_id='arn:aws:bedrock:us-east-1:297457984854:inference-profile/global.anthropic.claude-sonnet-4-20250514-v1:0',
            region_name=config.GOAL_AGENT_MODEL_REGION,
            provider=config.GOAL_AGENT_PROVIDER,
            temperature=config.GOAL_AGENT_TEMPERATURE,
        )

    def _create_agent_with_tools(self):
        tools = [
            create_goal, update_goal, get_in_progress_goal,
            list_goals, delete_goal, switch_goal_status, get_goal_by_id
        ]

        def prompt_builder():
            return self._create_system_prompt()

        return create_goal_subgraph(self.llm, tools, prompt_builder)

    def _create_system_prompt(self) -> str:
        return GOAL_AGENT_PROMPT

    async def process_query_with_agent(self, query: str, user_id) -> Command:
        agent = self._create_agent_with_tools()
        messages = [{"role": "user", "content": query}]

        agent_command = await agent.ainvoke({"messages": messages}, config={"recursion_limit": 10})
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
