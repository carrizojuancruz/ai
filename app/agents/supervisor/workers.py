from __future__ import annotations

import logging
import uuid
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import MessagesState

from app.core.app_state import get_goal_agent_graph, get_wealth_agent
from app.repositories.session_store import get_session_store
from app.utils.tools import get_config_value

from .finance_agent.agent import finance_agent as finance_worker

logger = logging.getLogger(__name__)


def _extract_text_from_content(content: str | list[dict[str, Any]] | dict[str, Any] | None) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                value = item.get("text") or item.get("content") or ""
                if isinstance(value, str):
                    parts.append(value)
        return "\n".join(parts).strip()
    return ""








async def wealth_agent(state: MessagesState, config: RunnableConfig) -> dict[str, Any]:
    """Wealth agent worker that handles wealth management and investment advice."""
    try:
        from app.core.app_state import get_wealth_agent_graph

        wealth_graph = get_wealth_agent_graph()
        logger.info("Using wealth_agent_graph instance")

        user_id = get_config_value(config, "user_id")

        import uuid
        unique_thread_id = f"wealth-task-{uuid.uuid4()}"

        wealth_config = {
            "configurable": {
                "thread_id": unique_thread_id,
                "user_id": user_id
            }
        }

        result = await wealth_graph.ainvoke(state, config=wealth_config)

        wealth_response = ""
        if "messages" in result and isinstance(result["messages"], list):
            for msg in reversed(result["messages"]):
                if (hasattr(msg, "content") and
                    getattr(msg, "name", None) == "wealth_agent" and
                    not getattr(msg, "response_metadata", {}).get("is_handoff_back", False) and
                    "Returning control to supervisor" not in str(msg.content)):
                    wealth_response = str(msg.content)
                    break

        if not wealth_response.strip():
            wealth_response = "Wealth analysis completed successfully."

        from app.agents.supervisor.handoff import create_handoff_back_messages
        handoff_messages = create_handoff_back_messages("wealth_agent", "supervisor")

        return {
            "messages": [
                {"role": "assistant", "content": wealth_response, "name": "wealth_agent"},
                handoff_messages[0],
            ]
        }

    except Exception as e:
        logger.error("Error in wealth_agent: %s", e)
        return {
            "messages": [{
                "role": "assistant",
                "content": f"I'm sorry, I had a problem processing your wealth request: {str(e)}",
                "name": "wealth_agent"
            }]
        }


async def goal_agent(state: MessagesState, config: RunnableConfig) -> dict[str, Any]:
    """Goal agent worker that handles financial goals management."""
    try:


        goal_graph = get_goal_agent_graph()
        user_id = get_config_value(config, "user_id")

        # Create unique thread for each supervisor handoff

        unique_thread_id = f"goal-task-{uuid.uuid4()}"

        goal_config = {
            "configurable": {
                "thread_id": unique_thread_id,
                "user_id": user_id
            }
        }

        result = await goal_graph.ainvoke(state, config=goal_config)

        goal_response = ""
        if "messages" in result and isinstance(result["messages"], list):
            for msg in reversed(result["messages"]):
                if (hasattr(msg, "content") and
                    getattr(msg, "name", None) == "goal_agent" and
                    not getattr(msg, "response_metadata", {}).get("is_handoff_back", False)):
                    goal_response = str(msg.content)
                    break

        if not goal_response.strip():
            goal_response = "Goal analysis completed successfully."

        from app.agents.supervisor.handoff import create_handoff_back_messages
        handoff_messages = create_handoff_back_messages("goal_agent", "supervisor")

        return {
            "messages": [
                {"role": "assistant", "content": goal_response, "name": "goal_agent"},
                handoff_messages[0],
            ]
        }

    except Exception as e:
        logger.error("Error in goal_agent: %s", e)
        return {
            "messages": [{
                "role": "assistant",
                "content": f"I'm sorry, I had a problem processing your goal request: {str(e)}",
                "name": "goal_agent"
            }]
        }


async def wealth_router(state: MessagesState, config: RunnableConfig) -> dict[str, Any]:
    """Route to wealth agent with validation logic."""
    try:
        return await wealth_agent(state, config)
    except Exception as e:
        logger.error(f"wealth_router: error - {e}")
        content = "I'm having trouble accessing wealth information right now. Please try again."
        return {"messages": [{"role": "assistant", "content": content, "name": "wealth_agent"}]}


async def finance_router(state: MessagesState, config: RunnableConfig) -> dict[str, Any]:
    """Short-circuit when no accounts; else forward to finance_agent."""
    try:
        thread_id = get_config_value(config, "thread_id")

        if not thread_id:
            logger.warning("finance_router: missing thread_id, defaulting to no accounts")
            content = "FINANCE_STATUS: NO_ACCOUNTS_CONNECTED — COULDNT FIND A THREAD ID"
            return {"messages": [{"role": "assistant", "content": content, "name": "finance_agent"}]}

        session_store = get_session_store()
        sess = await session_store.get_session(thread_id)

        has_accounts = bool(sess.get("has_financial_accounts", False)) if isinstance(sess, dict) else False

        if not has_accounts:
            content = "FINANCE_STATUS: NO_ACCOUNTS_CONNECTED — You don't have any financial accounts connected yet. To get started, go to the Connected Accounts menu and connect your accounts through Plaid."
            return {"messages": [{"role": "assistant", "content": content, "name": "finance_agent"}]}

        return await finance_worker(state, config)

    except Exception as e:
        logger.error(f"finance_router: error - {e}")
        content = "I'm having trouble accessing your financial information right now. Please try again, or connect your accounts through the Connected Accounts menu if you haven't already."
        return {"messages": [{"role": "assistant", "content": content, "name": "finance_agent"}]}
