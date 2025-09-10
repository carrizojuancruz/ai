from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import MessagesState

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
                handoff_messages[1]
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
