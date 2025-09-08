from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import MessagesState

from app.utils.welcome import call_llm

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


async def math_agent(state: MessagesState) -> dict[str, Any]:
    system: str = (
        "You are a math assistant. Compute the result. Return 'The result is <result>'."
    )
    prompt: str = _get_last_user_message_text(state["messages"]) or "Answer the math question briefly."
    content: str = await call_llm(system, prompt)
    content = content or "I could not compute that right now."
    return {"messages": [{"role": "assistant", "content": content, "name": "math_agent"}]}


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
