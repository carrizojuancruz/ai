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





async def wealth_agent(state: MessagesState, config: RunnableConfig) -> dict[str, Any]:
    """Wealth agent worker that handles wealth management and investment advice."""
    try:
        wealth_agent = compile_wealth_agent_graph()

        result = await wealth_agent.ainvoke(state, config=config)

        wealth_response = ""
        if "messages" in result and isinstance(result["messages"], list):
            for msg in reversed(result["messages"]):
                if hasattr(msg, "content"):
                    content = msg.content
                    if isinstance(content, list):
                        text_parts = []
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                text_parts.append(item.get("text", ""))
                        wealth_response = "\n".join(text_parts) if text_parts else str(content)
                    else:
                        wealth_response = str(content)
                    break
                elif isinstance(msg, dict) and msg.get("role") == "assistant":
                    wealth_response = str(msg.get("content", ""))
                    break
        if not wealth_response.strip():
            wealth_response = "Wealth analysis completed successfully."

        last_message = state["messages"][-1]
        if isinstance(last_message, HumanMessage):
            task_content = getattr(last_message, "content", "Unknown task")
        elif isinstance(last_message, dict):
            task_content = last_message.get("content", "Unknown task")
        else:
            task_content = str(last_message)

        analysis_response = f"""
        ===== WEALTH AGENT TASK COMPLETED =====

        Task Analyzed: {task_content}...

        Analysis Results:
        {wealth_response}

        STATUS: WEALTH AGENT ANALYSIS COMPLETE
        This wealth agent analysis is provided to the supervisor for final user response formatting.
        """

        from app.agents.supervisor.handoff import create_handoff_back_messages
        handoff_messages = create_handoff_back_messages("wealth_agent", "supervisor")

        return {
            "messages": [
                {"role": "assistant", "content": analysis_response, "name": "wealth_agent"},
                handoff_messages[0]
            ]
        }

    except Exception as e:
        logger.error("Wealth agent failed: %s", e)
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
        # Get the goal_agent graph
        from .goal_agent.agent import compile_goal_agent_graph

        goal_graph = compile_goal_agent_graph()

        # Process message through the goal_agent graph with full conversation context
        result = await goal_graph.ainvoke(state, config=config)

        goal_response = ""
        if "messages" in result and isinstance(result["messages"], list):
            for msg in reversed(result["messages"]):
                if hasattr(msg, "content"):
                    content = msg.content
                    if isinstance(content, list):
                        text_parts = []
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                text_parts.append(item.get("text", ""))
                        goal_response = "\n".join(text_parts) if text_parts else str(content)
                    else:
                        goal_response = str(content)
                    break
                elif isinstance(msg, dict) and msg.get("role") == "assistant":
                    goal_response = str(msg.get("content", ""))
                    break
        if not goal_response.strip():
            goal_response = "Goal analysis completed successfully."

        analysis_response = f"""
        GOAL AGENT COMPLETE:

        Task Analyzed: {goal_response}...

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
