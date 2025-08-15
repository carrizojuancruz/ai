from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import MessagesState


def research_agent(state: MessagesState) -> dict[str, Any]:
    prompt_messages = [
        SystemMessage(content="You are a helpful research agent. Return a short factual summary."),
    ] + state["messages"]
    # Stubbed behavior: echo the last human message with a canned response
    last = next((m for m in reversed(prompt_messages) if isinstance(m, HumanMessage)), None)
    content = (
        f"[research] acknowledging: {getattr(last, 'content', '')}" if last else "[research] ready"
    )
    return {"messages": [{"role": "assistant", "content": content, "name": "research_agent"}]}


def math_agent(state: MessagesState) -> dict[str, Any]:
    prompt_messages = [
        SystemMessage(content="You are a math agent. Compute or summarize briefly; no steps."),
    ] + state["messages"]
    last = next((m for m in reversed(prompt_messages) if isinstance(m, HumanMessage)), None)
    content = (
        f"[math] acknowledging: {getattr(last, 'content', '')}" if last else "[math] ready"
    )
    return {"messages": [{"role": "assistant", "content": content, "name": "math_agent"}]}


