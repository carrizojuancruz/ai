from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import MessagesState

from app.repositories.session_store import get_session_store
from app.utils.tools import get_config_value

from .finance_agent.agent import finance_agent as finance_worker
from .wealth_agent.agent import compile_wealth_agent_graph

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





async def wealth_agent(state: MessagesState) -> dict[str, Any]:
    try:
        wealth_agent = compile_wealth_agent_graph()
        result = await wealth_agent.ainvoke(state)
        logger.info(f"Wealth agent result: {result}")

        # Extract the wealth agent's response - get the LAST assistant message
        wealth_response = ""
        if "messages" in result:
            assistant_messages = []
            for msg in result["messages"]:
                if isinstance(msg, dict) and msg.get("role") == "assistant":
                    assistant_messages.append(msg.get("content", ""))
                elif hasattr(msg, "content") and getattr(msg, "name", None) == "wealth_agent":
                    assistant_messages.append(str(msg.content))

            # Get the last assistant message (the final response after search)
            if assistant_messages:
                wealth_response = assistant_messages[-1]

        # Create proper handoff messages to signal completion to supervisor
        from app.agents.supervisor.handoff import create_handoff_back_messages
        handoff_messages = create_handoff_back_messages("wealth_agent", "supervisor")

        return {
            "messages": [
                {"role": "assistant", "content": wealth_response, "name": "wealth_agent"},
                handoff_messages[0],
                handoff_messages[1]
            ]
        }
    except Exception as e:
        logger.error("Wealth agent failed: %s", e)
        content = "I'm having trouble accessing financial information right now. Please try again later."
        return {"messages": [{"role": "assistant", "content": content, "name": "wealth_agent"}]}


async def goal_agent(state: MessagesState, config: RunnableConfig) -> dict[str, Any]:
    """Goal agent worker that handles financial goals management."""
    try:
        # Get the goal_agent graph
        from .goal_agent.agent import compile_goal_agent_graph

        goal_graph = compile_goal_agent_graph()

        # Process message through the goal_agent graph with full conversation context
        result = await goal_graph.ainvoke(state, config=config)

        # Get the last user message content safely
        last_message = state["messages"][-1]
        if isinstance(last_message, HumanMessage):
            task_content = getattr(last_message, "content", "Unknown task")
        elif isinstance(last_message, dict):
            task_content = last_message.get("content", "Unknown task")
        else:
            task_content = str(last_message)

        analysis_response = f"""
        GOAL AGENT COMPLETE:

        Task Analyzed: {task_content}...

        Analysis Results:
        {result}

        This goal agent is provided to the supervisor for final user response formatting.
        """

        from app.agents.supervisor.handoff import create_handoff_back_messages
        handoff_messages = create_handoff_back_messages("goal_agent", "supervisor")

        # Return the result in the expected format by MessagesState
        return {
            "messages": [
                {"role": "assistant", "content": analysis_response, "name": "goal_agent"},
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

        return await finance_worker(state, config)

    except Exception as e:
        logger.error(f"finance_router: error - {e}")
        content = "I'm having trouble accessing your financial information right now. Please try again, or connect your accounts through the Connected Accounts menu if you haven't already."
        return {"messages": [{"role": "assistant", "content": content, "name": "finance_agent"}]}
