from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import MessagesState

from app.repositories.session_store import get_session_store
from app.utils.tools import get_config_value

from .subagents.wealth_agent.agent import compile_wealth_agent_graph

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


def _get_last_user_message_text(messages: list[HumanMessage | dict[str, Any]]) -> str:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return _extract_text_from_content(getattr(m, "content", ""))
        if isinstance(m, dict) and m.get("role") == "user":
            return _extract_text_from_content(m.get("content"))
    return ""




async def wealth_agent(state: MessagesState) -> dict[str, Any]:
    try:
        wealth_agent = compile_wealth_agent_graph()
        result = await wealth_agent.ainvoke(state)
        return result
    except Exception as e:
        logger.error(f"Wealth agent failed: {e}")
        content = "I'm having trouble accessing financial information right now. Please try again later."
        return {"messages": [{"role": "assistant", "content": content, "name": "wealth_agent"}]}


async def goal_agent(state: MessagesState, config: RunnableConfig) -> dict[str, Any]:
    """Goal agent worker that handles financial goals management."""
    try:
        # Get the goal_agent graph
        from .subagents.goal_agent.agent import compile_goal_agent_graph

        goal_graph = compile_goal_agent_graph()

        # Process message through the goal_agent graph with full conversation context
        result = await goal_graph.ainvoke(state, config=config)

        # Return the result in the expected format by MessagesState
        return result

    except Exception as e:
        print(f"Error in goal_agent: {e}")
        return {
            "messages": [{
                "role": "assistant",
                "content": f"I'm sorry, I had a problem processing your goal request: {str(e)}",
                "name": "goal_agent"
            }]
        }


async def finance_router(state: MessagesState, config: RunnableConfig) -> dict[str, Any]:
    """Short-circuit when no accounts; else forward to finance_agent."""
    try:
        thread_id = get_config_value(config, "thread_id")

        if not thread_id:
            logger.warning("finance_router: missing thread_id, defaulting to no accounts")
            content = "FINANCE_STATUS: NO_ACCOUNTS_CONNECTED — You don't have any financial accounts connected yet. To get started, go to the Connected Accounts menu and connect your accounts through Plaid."
            return {"messages": [{"role": "assistant", "content": content, "name": "finance_agent"}]}

        session_store = get_session_store()
        sess = await session_store.get_session(thread_id)

        has_accounts = bool(sess.get("has_financial_accounts", False)) if isinstance(sess, dict) else False

        if not has_accounts:
            content = "FINANCE_STATUS: NO_ACCOUNTS_CONNECTED — You don't have any financial accounts connected yet. To get started, go to the Connected Accounts menu and connect your accounts through Plaid."
            return {"messages": [{"role": "assistant", "content": content, "name": "finance_agent"}]}

        from app.agents.supervisor.finance_agent.agent import finance_agent as finance_worker
        return await finance_worker(state, config)

    except Exception as e:
        logger.error(f"finance_router: error - {e}")
        content = "I'm having trouble accessing your financial information right now. Please try again, or connect your accounts through the Connected Accounts menu if you haven't already."
        return {"messages": [{"role": "assistant", "content": content, "name": "finance_agent"}]}
