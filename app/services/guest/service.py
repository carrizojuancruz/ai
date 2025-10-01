from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from app.agents.guest import get_guest_graph
from app.core.app_state import (
    get_sse_queue,
    get_thread_state,
    register_thread,
    set_thread_state,
)
from app.core.config import config
from app.repositories.session_store import get_session_store

logger = logging.getLogger(__name__)

HARDCODED_GUEST_WELCOME = "So tell me, what's on your mind today?"

GUARDRAIL_INTERVENED_MARKER = "[GUARDRAIL_INTERVENED]"
GUARDRAIL_USER_PLACEHOLDER = "THIS MESSAGE HIT THE BEDROCK GUARDRAIL"

LAST_MESSAGE_NUDGE_TEXT = (
    "Hey, by the way, our chat here is a bit limited...\n\n"
    "If you sign up or log in, I can remember everything we talk about and help you reach your goals. Sounds good?"
)

def _wrap(content: str, count: int, max_messages: int) -> dict[str, Any]:
    content = (content or "").strip()
    count = max(1, count)
    if count >= max_messages:
        return {
            "id": f"message_{max_messages}",
            "type": "login_wall_trigger",
            "content": content,
            "message_count": max_messages,
            "can_continue": False,
            "trigger_login_wall": True,
        }
    return {
        "id": f"message_{count}",
        "type": "normal_conversation",
        "content": content,
        "message_count": count,
        "can_continue": True,
    }

class GuestService:
    def __init__(self) -> None:
        try:
            self.max_messages = max(1, config.GUEST_MAX_MESSAGES)
        except Exception:
            self.max_messages = 5
        self.graph = get_guest_graph()

    def _has_guardrail_intervention(self, text: str) -> bool:
        if not isinstance(text, str):
            return False
        return GUARDRAIL_INTERVENED_MARKER in text

    def _strip_guardrail_marker(self, text: str) -> str:
        if not isinstance(text, str):
            return ""
        start = text.find(GUARDRAIL_INTERVENED_MARKER)
        if start != -1:
            return text[:start].rstrip()
        return text

    async def initialize(self) -> dict[str, Any]:
        thread_id = str(uuid4())

        state: dict[str, Any] = {
            "conversation_id": thread_id,
            "message_count": 0,
            "messages": [],
            "ended": False,
        }

        register_thread(thread_id, state)
        queue = get_sse_queue(thread_id)

        session_store = get_session_store()
        await session_store.set_session(thread_id, {"guest": True})

        await queue.put({"event": "conversation.started", "data": {"thread_id": thread_id}})

        accumulated = HARDCODED_GUEST_WELCOME
        await queue.put({"event": "token.delta", "data": {"text": HARDCODED_GUEST_WELCOME}})

        content = (
            accumulated.strip()
            or "Hi! Quick heads up: this guest chat won't be remembered. What money question can I help with now?"
        )
        state["message_count"] = 1
        state["messages"].append({"role": "assistant", "content": content})

        payload = _wrap(content, state["message_count"], self.max_messages)
        await queue.put({"event": "message.completed", "data": payload})

        if state["message_count"] >= self.max_messages:
            state["ended"] = True
            await queue.put(
                {"event": "conversation.ended", "data": {"thread_id": thread_id, "limit": self.max_messages}}
            )

        set_thread_state(thread_id, state)

        return {"thread_id": thread_id, "welcome": payload, "sse_url": f"/guest/sse/{thread_id}"}

    async def process_message(self, *, thread_id: str, text: str) -> dict[str, Any]:
        state = get_thread_state(thread_id)
        if state is None:
            raise HTTPException(status_code=404, detail="Thread not found")

        queue = get_sse_queue(thread_id)

        if state.get("ended"):
            await queue.put(
                {
                    "event": "message.completed",
                    "data": {
                        "id": f"message_{state.get('message_count', 0)}",
                        "type": "login_wall_trigger",
                        "content": "This guest conversation has ended. Please sign up or log in to continue.",
                        "message_count": state.get("message_count", 0),
                        "can_continue": False,
                        "trigger_login_wall": True,
                    },
                }
            )
            return {"status": "ended"}

        prior = state.get("messages", [])
        inputs = {"messages": prior + [{"role": "user", "content": text}]}

        accumulated = ""
        try:
            async for ev in self.graph.astream_events(
                inputs,
                version="v1",
                config={
                    "run_name": "guest.message",
                    "tags": ["guest"],
                    "metadata": {"thread_id": thread_id, "phase": "message"},
                },
            ):
                if ev.get("event") == "on_chat_model_stream":
                    data = ev.get("data", {})
                    chunk = data.get("chunk")
                    try:
                        content = getattr(chunk, "content", "")
                        if isinstance(content, list):
                            token_text = "".join([str(p.get("text", "")) for p in content if isinstance(p, dict)])
                        else:
                            token_text = str(content or "")
                    except Exception:
                        token_text = ""
                    if token_text:
                        accumulated += token_text
                        await queue.put({"event": "token.delta", "data": {"text": token_text}})
        except Exception:
            pass

        content = accumulated.strip()

        if self._has_guardrail_intervention(content):
            logger.info("[GUEST] Guardrail intervention detected, removing offending message from state")

            prior_messages = state.get("messages", [])
            if prior_messages and prior_messages[-1].get("role") == "user":
                prior_messages[-1] = {"role": "user", "content": GUARDRAIL_USER_PLACEHOLDER}
                state["messages"] = prior_messages
                logger.info("[GUEST] Replaced offending user message with guardrail placeholder")

            state.setdefault("messages", []).append({"role": "assistant", "content": content})

        else:
            state.setdefault("messages", []).append({"role": "user", "content": text})
            state.setdefault("messages", []).append({"role": "assistant", "content": content})

        next_count = int(state.get("message_count", 0)) + 1

        final_content = content
        if next_count >= self.max_messages:
            if LAST_MESSAGE_NUDGE_TEXT not in final_content:
                final_content = (final_content + "\n\n" + LAST_MESSAGE_NUDGE_TEXT).strip()
                await queue.put({"event": "token.delta", "data": {"text": "\n\n" + LAST_MESSAGE_NUDGE_TEXT}})
            messages = state.get("messages", [])
            for i in range(len(messages) - 1, -1, -1):
                msg = messages[i]
                if msg.get("role") == "assistant":
                    messages[i] = {"role": "assistant", "content": final_content}
                    break
            state["messages"] = messages

        content = final_content
        payload = _wrap(content, next_count, self.max_messages)

        await queue.put({"event": "message.completed", "data": payload})

        state["message_count"] = next_count

        if state["message_count"] >= self.max_messages:
            state["ended"] = True
            await queue.put(
                {"event": "conversation.ended", "data": {"thread_id": thread_id, "limit": self.max_messages}}
            )

        set_thread_state(thread_id, state)
        return {"status": "accepted"}

guest_service = GuestService()
