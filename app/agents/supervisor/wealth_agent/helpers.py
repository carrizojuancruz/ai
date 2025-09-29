from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from app.agents.supervisor.handoff import create_handoff_back_messages


def extract_text_from_content(content: Any) -> str:
    """Universal content extraction from various formats."""
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
    return str(content) if content else ""


def get_last_user_message_text(messages: list[HumanMessage | dict[str, Any]]) -> str:
    """Extract latest user query from message history."""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return extract_text_from_content(getattr(m, "content", ""))
        if isinstance(m, dict) and m.get("role") == "user":
            return extract_text_from_content(m.get("content"))
    return ""


def get_user_id_from_messages(messages: list[HumanMessage | dict[str, Any]]) -> Optional[UUID]:
    """Extract user ID from message metadata."""
    for m in reversed(messages):
        if isinstance(m, dict) and m.get("role") == "user":
            user_id = m.get("user_id")
            if user_id:
                try:
                    return UUID(user_id) if isinstance(user_id, str) else user_id
                except (ValueError, TypeError):
                    continue
    return None


def create_error_command(error_message: str) -> Command:
    """Standardized error response with proper handoff."""
    handoff_messages = create_handoff_back_messages("wealth_agent", "supervisor")
    return Command(
        update={
            "messages": [
                {"role": "assistant", "content": error_message, "name": "wealth_agent"},
                handoff_messages[0],
            ]
        },
        goto="supervisor",
    )
