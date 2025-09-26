from __future__ import annotations

import datetime
from typing import Any, Optional
from uuid import UUID

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from app.agents.supervisor.handoff import create_handoff_back_messages


def extract_text_from_content(content: Any) -> str:
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
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return extract_text_from_content(getattr(m, "content", ""))
        if isinstance(m, dict) and m.get("role") == "user":
            return extract_text_from_content(m.get("content"))
    return ""


def get_user_id_from_messages(messages: list[HumanMessage | dict[str, Any]]) -> Optional[UUID]:
    for m in reversed(messages):
        if isinstance(m, dict) and m.get("role") == "user":
            user_id = m.get("user_id")
            if user_id:
                try:
                    return UUID(user_id) if isinstance(user_id, str) else user_id
                except (ValueError, TypeError):
                    continue
    return None


def serialize_sample_row(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        return row
    serialized: dict[str, Any] = {}
    for k, v in row.items():
        if hasattr(v, "is_finite"):
            serialized[k] = float(v)
        elif isinstance(v, datetime.date):
            serialized[k] = v.isoformat()
        elif isinstance(v, UUID) or hasattr(v, "__class__") and "UUID" in str(type(v)):
            serialized[k] = str(v)
        else:
            serialized[k] = v
    return serialized


def rows_to_json(rows: list[dict[str, Any]]) -> str:
    import json

    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))


def create_error_command(error_message: str) -> Command:
    handoff_messages = create_handoff_back_messages("finance_agent", "supervisor")
    return Command(
        update={
            "messages": [
                {"role": "assistant", "content": error_message, "name": "finance_agent"},
                handoff_messages[0],
            ]
        },
        goto="supervisor",
    )


