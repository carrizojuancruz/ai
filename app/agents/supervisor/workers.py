from __future__ import annotations

import logging
import uuid
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import MessagesState
from langgraph.types import Command

from app.agents.supervisor.finance_agent.tools import PLAID_REQUIRED_STATUS_PREFIX
from app.repositories.session_store import get_session_store
from app.utils.tools import get_config_value

from .finance_agent.agent import finance_agent as finance_worker

logger = logging.getLogger(__name__)


async def wealth_agent(state: MessagesState, config: RunnableConfig) -> dict[str, Any]:
    """Wealth agent worker that handles wealth management and investment advice."""
    try:
        from app.agents.supervisor.wealth_agent.subgraph import RECURSION_LIMIT
        from app.core.app_state import get_wealth_agent_graph

        wealth_graph = get_wealth_agent_graph()
        logger.info("Using wealth_agent_graph instance")

        user_id = get_config_value(config, "user_id")

        import uuid
        unique_thread_id = f"wealth-task-{uuid.uuid4()}"

        wealth_config = {
            "recursion_limit": RECURSION_LIMIT,
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
        # Extract Langfuse callback from supervisor config if available
        langfuse_callback = config.get("configurable", {}).get("langfuse_callback_goals")
        callbacks_list = [langfuse_callback] if langfuse_callback else []

        # Import here to avoid circular dependencies
        from app.agents.supervisor.goal_agent.agent import get_goal_agent

        # Use singleton GoalAgent instance (refresh with callbacks when provided)
        goal_agent_instance = get_goal_agent(callbacks=callbacks_list if callbacks_list else None)
        goal_graph = goal_agent_instance._create_agent_with_tools()

        user_id = get_config_value(config, "user_id")

        # Create unique thread for each supervisor handoff
        unique_thread_id = f"goal-task-{uuid.uuid4()}"

        # Propagate callbacks through config
        goal_config = {
            "configurable": {
                "thread_id": unique_thread_id,
                "user_id": user_id
            },
            "callbacks": callbacks_list
        }

        logger.info("[Langfuse][goal] Invoking goal_agent with %d callbacks", len(callbacks_list))
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
    """Route to finance_agent and surface Plaid-only gating when required."""
    try:
        thread_id = get_config_value(config, "thread_id")

        if not thread_id:
            logger.warning("finance_router: missing thread_id, defaulting to no accounts")
            content = (
                "FINANCE_STATUS: NO_ACCOUNTS_CONNECTED — Could not determine your thread. "
                "Please reconnect and try again."
            )
            return {"messages": [{"role": "assistant", "content": content, "name": "finance_agent"}]}

        session_store = get_session_store()
        sess = await session_store.get_session(thread_id) or {}

        has_plaid_accounts = bool(
            sess.get("has_plaid_accounts", sess.get("has_financial_accounts", False))
        )

        result = await finance_worker(state, config)
        return _attach_plaid_navigation_event_if_needed(result, has_plaid_accounts)

    except Exception as e:
        logger.error(f"finance_router: error - {e}")
        content = "I'm having trouble accessing your financial information right now. Please try again, or connect your accounts through the Connected Accounts menu if you haven't already."
        return {"messages": [{"role": "assistant", "content": content, "name": "finance_agent"}]}


def _attach_plaid_navigation_event_if_needed(result: Any, has_plaid_accounts: bool) -> Any:
    """Append connect-accounts navigation event when plaid data is required but unavailable."""
    if has_plaid_accounts:
        return result

    update_block: dict[str, Any] | None = None
    if isinstance(result, Command):
        if result.update is None or not isinstance(result.update, dict):
            result.update = {}
        update_block = result.update
    elif isinstance(result, dict):
        update_block = result

    messages = _extract_messages_from_result(result)
    if not _messages_require_plaid_data(messages):
        return result

    event_payload = {
        "event": "navigation.connected-accounts",
        "data": {
            "message": "Connect an account (Financial Info → Connected Accounts) to enable live transaction insights.",
            "action": "connect_accounts",
        },
    }
    if update_block is not None:
        nav_events = update_block.setdefault("navigation_events", [])
        if event_payload not in nav_events:
            nav_events.append(event_payload)
        return result

    return Command(update={"navigation_events": [event_payload]}, goto=getattr(result, "goto", None))


def _messages_require_plaid_data(messages: list[Any]) -> bool:
    """Detect whether any message indicates a plaid-specific requirement."""
    for msg in messages or []:
        content = getattr(msg, "content", None)
        if content is None and isinstance(msg, dict):
            content = msg.get("content")
        if isinstance(content, str) and PLAID_REQUIRED_STATUS_PREFIX in content:
            return True
    return False


def _extract_messages_from_result(result: Any) -> list[Any]:
    if isinstance(result, Command):
        update_block = result.update if isinstance(result.update, dict) else {}
        if isinstance(update_block, dict):
            messages = update_block.get("messages")
            return messages if isinstance(messages, list) else []
        return []
    if isinstance(result, dict):
        messages = result.get("messages")
        return messages if isinstance(messages, list) else []
    return []
