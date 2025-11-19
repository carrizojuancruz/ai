from __future__ import annotations

import logging
from uuid import UUID

from langchain_cerebras import ChatCerebras
from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from app.core.app_state import get_wealth_agent
from app.core.config import config
from app.observability.logging_config import configure_logging

from .helpers import create_error_command
from .tools import search_kb

logger = logging.getLogger(__name__)


class WealthAgent:
    """Wealth agent for searching knowledge base and providing financial information."""

    def __init__(self):
        logger.info("Initializing WealthAgent with Cerebras models")

        self.llm = ChatCerebras(
            model="gpt-oss-120b",
            api_key=config.CEREBRAS_API_KEY,
            temperature=config.WEALTH_AGENT_TEMPERATURE or 0.4,
        )

    async def process_query_with_agent(self, query: str, user_id: UUID) -> Command:
        """Process wealth queries and return Command from agent execution."""
        try:
            logger.info(f"Processing wealth query with agent for user {user_id}: {query}")

            agent = self._create_agent_with_tools()
            logger.info("Created fresh LangGraph agent for supervisor task")

            messages = [HumanMessage(content=query)]

            logger.info(f"Starting LangGraph agent execution for user {user_id}")
            initial_state = {"messages": messages, "tool_call_count": 0}
            agent_command = await agent.ainvoke(initial_state, config={"recursion_limit": 10})
            logger.info(f"Agent execution completed for user {user_id}")

            return agent_command

        except Exception as e:
            logger.error(f"Wealth agent error for user {user_id}: {e}")
            return create_error_command("I encountered an error while processing your wealth query. Please try again.")

    def _create_system_prompt(self, user_context: dict = None) -> str:
        """Create system prompt for the wealth agent."""
        from app.services.llm.prompt_loader import prompt_loader
        return prompt_loader.load("wealth_agent_system_prompt", user_context=user_context)

    def _create_agent_with_tools(self):
        """Create wealth agent with knowledge base search tool."""
        logger.info("Creating wealth agent with search_kb tool")

        tools = [search_kb]

        def prompt_builder() -> str:
            return self._create_system_prompt()

        from .subgraph import create_wealth_subgraph
        return create_wealth_subgraph(self.llm, tools, prompt_builder)


def compile_wealth_agent_graph() -> CompiledStateGraph:
    """Compile the wealth agent graph."""
    configure_logging()

    wealth_agent_instance = WealthAgent()
    return wealth_agent_instance._create_agent_with_tools()


async def wealth_agent(state, config):
    """Wealth agent worker function that returns Command like finance agent."""
    try:
        from app.agents.supervisor.handoff import create_handoff_back_messages
        from app.utils.tools import get_config_value

        from .helpers import (
            create_error_command,
            get_last_user_message_text,
            get_user_id_from_messages,
        )

        user_id = get_config_value(config, "user_id")
        if not user_id:
            user_id = get_user_id_from_messages(state["messages"])

        query = get_last_user_message_text(state["messages"])

        if not user_id:
            logger.warning("No user_id found in wealth agent request")
            return create_error_command("ERROR: Cannot access wealth data without user identification.")

        if not query:
            logger.warning("No task description found in wealth agent request")
            return create_error_command("ERROR: No task description provided for analysis.")

        wealth_agent_instance = get_wealth_agent()
        agent_command = await wealth_agent_instance.process_query_with_agent(query, user_id)

        return agent_command

    except Exception as e:
        logger.error(f"Wealth agent critical error: {e}")

        from app.agents.supervisor.handoff import create_handoff_back_messages

        error_analysis = f"I'm sorry, I had a problem processing your wealth request: {str(e)}"
        handoff_messages = create_handoff_back_messages("wealth_agent", "supervisor")

        return Command(
            update={
                "messages": [
                    {"role": "assistant", "content": error_analysis, "name": "wealth_agent"},
                    handoff_messages[0],
                ]
            },
            goto="supervisor",
        )
