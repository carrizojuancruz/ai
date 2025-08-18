from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.graph import MessagesState

from app.utils.welcome import call_llm


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

async def research_agent(state: MessagesState) -> dict[str, Any]:
    system: str = (
        "You are a helpful research agent. Return a short, factual, neutral summary in <= 60 words."
    )
    prompt: str = _get_last_user_message_text(state["messages"]) or "Provide a short factual summary."
    content: str = await call_llm(system, prompt)
    content = content or "I could not retrieve information at this time."
    return {"messages": [{"role": "assistant", "content": content, "name": "research_agent"}]}


async def math_agent(state: MessagesState) -> dict[str, Any]:
    system: str = (
        "You are a math assistant. Compute the result. Return 'The result is <result>'."
    )
    prompt: str = _get_last_user_message_text(state["messages"]) or "Answer the math question briefly."
    content: str = await call_llm(system, prompt)
    content = content or "I could not compute that right now."
    return {"messages": [{"role": "assistant", "content": content, "name": "math_agent"}]}


