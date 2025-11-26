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
    "Hey, our chat here is coming to an end, but how about keeping it going?\n\n"
    "If you sign up or log in, I can start remembering our chats and guide you better. It's free for 30 days. Sounds good?"
)
SAFE_FALLBACK_ASSISTANT_REPLY = "Could you rephrase that a bit so I can help better?"


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
        return isinstance(text, str) and GUARDRAIL_INTERVENED_MARKER in text

    def _strip_guardrail_marker(self, text: str) -> str:
        if not isinstance(text, str):
            return ""
        idx = text.find(GUARDRAIL_INTERVENED_MARKER)
        return text[:idx].rstrip() if idx != -1 else text

    async def initialize(self) -> dict[str, Any]:
        thread_id = str(uuid4())
        state = {
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
        await queue.put({"event": "token.delta", "data": {"text": HARDCODED_GUEST_WELCOME}})

        welcome_content = HARDCODED_GUEST_WELCOME.strip() or (
            "Hi! Quick heads up: this guest chat won't be remembered. What money question can I help with now?"
        )
        state["message_count"] = 1
        state["messages"].append({"role": "assistant", "content": welcome_content})

        payload = _wrap(welcome_content, state["message_count"], self.max_messages)
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

        prior_messages = state.get("messages", [])
        real_messages = [
            msg
            for msg in prior_messages
            if not (
                msg.get("role") == "assistant" and msg.get("content", "").strip() == HARDCODED_GUEST_WELCOME.strip()
            )
        ]
        inputs = {"messages": real_messages + [{"role": "user", "content": text}]}

        accumulated = ""
        latest_response_text = ""
        configurable = {"thread_id": thread_id, "checkpoint_ns": "guest"}

        try:
            logger.info(
                "[GUEST][CKPT] Starting graph run thread_id=%s message_idx=%s ended=%s",
                thread_id,
                state.get("message_count"),
                state.get("ended"),
            )
            async for ev in self.graph.astream_events(
                inputs,
                version="v1",
                config={
                    "run_name": "guest.message",
                    "tags": ["guest"],
                    "metadata": {"thread_id": thread_id, "phase": "message"},
                    "configurable": configurable,
                },
            ):
                if ev.get("event") == "on_chat_model_stream":
                    data = ev.get("data", {}) or {}
                    chunk = data.get("chunk")
                    try:
                        chunk_content = getattr(chunk, "content", "")
                        if isinstance(chunk_content, list):
                            token_text = "".join(
                                str(piece.get("text", "")) for piece in chunk_content if isinstance(piece, dict)
                            )
                        else:
                            token_text = str(chunk_content or "")
                    except Exception:
                        token_text = ""
                    if token_text:
                        accumulated += token_text
                        await queue.put({"event": "token.delta", "data": {"text": token_text}})
                else:
                    try:
                        data = ev.get("data", {}) or {}
                        output = data.get("output", {}) if isinstance(data, dict) else {}
                        messages_out = output.get("messages") if isinstance(output, dict) else None
                        if isinstance(messages_out, list) and messages_out:
                            for msg in reversed(messages_out):
                                content_list = getattr(msg, "content", None)
                                if isinstance(content_list, list):
                                    for item in reversed(content_list):
                                        if isinstance(item, dict) and item.get("type") == "text":
                                            candidate = item.get("text", "")
                                            if candidate and candidate.strip():
                                                latest_response_text = candidate
                                                break
                                    if latest_response_text:
                                        break
                                elif isinstance(content_list, str) and content_list.strip():
                                    latest_response_text = content_list
                                    break
                    except Exception as e:
                        logger.debug("[GUEST] Failed to parse fallback text from event: %s", e)
        except Exception as e:
            logger.exception("[GUEST] Error while streaming guest message: %s", e)
        else:
            logger.info(
                "[GUEST][CKPT] Graph run completed thread_id=%s tokens_emitted=%d",
                thread_id,
                len(accumulated),
            )

        final_text = accumulated.strip() or (latest_response_text.strip() if latest_response_text else "")

        if not final_text:
            try:
                result = await self.graph.ainvoke(
                    inputs,
                    config={
                        "run_name": "guest.message.fallback",
                        "tags": ["guest", "fallback"],
                        "metadata": {"thread_id": thread_id, "phase": "message_fallback"},
                        "configurable": configurable,
                    },
                )
                fallback_text = ""
                try:
                    messages_out = None
                    if isinstance(result, dict):
                        messages_out = result.get("messages")
                    if messages_out is None:
                        messages_out = getattr(result, "messages", None)
                    if isinstance(messages_out, list):
                        for msg in reversed(messages_out):
                            content_list = getattr(msg, "content", None)
                            if isinstance(content_list, list):
                                for item in reversed(content_list):
                                    if isinstance(item, dict) and item.get("type") == "text":
                                        candidate = item.get("text", "")
                                        if candidate and candidate.strip():
                                            fallback_text = candidate
                                            break
                                if fallback_text:
                                    break
                            elif isinstance(content_list, str) and content_list.strip():
                                fallback_text = content_list
                                break
                except Exception as e:
                    logger.debug("[GUEST] Failed to parse text from non-stream fallback result: %s", e)
                if fallback_text and fallback_text.strip():
                    final_text = fallback_text.strip()
                    await queue.put({"event": "token.delta", "data": {"text": final_text}})
            except Exception as e:
                logger.exception("[GUEST] Non-stream fallback failed: %s", e)
            else:
                logger.info("[GUEST][CKPT] Fallback invoke succeeded thread_id=%s", thread_id)

        if not final_text:
            final_text = SAFE_FALLBACK_ASSISTANT_REPLY
            await queue.put({"event": "token.delta", "data": {"text": final_text}})

        # Guardrail intervention logic
        if self._has_guardrail_intervention(final_text):
            logger.info("[GUEST] Guardrail intervention detected, removing offending message from state")
            prior_msgs = state.get("messages", [])
            if prior_msgs and prior_msgs[-1].get("role") == "user":
                prior_msgs[-1] = {"role": "user", "content": GUARDRAIL_USER_PLACEHOLDER}
                state["messages"] = prior_msgs
                logger.info("[GUEST] Replaced offending user message with guardrail placeholder")
            state.setdefault("messages", []).append({"role": "assistant", "content": final_text})
        else:
            state.setdefault("messages", []).append({"role": "user", "content": text})
            state.setdefault("messages", []).append({"role": "assistant", "content": final_text})

        next_count = int(state.get("message_count", 0)) + 1

        nudge_content = final_text
        if next_count >= self.max_messages:
            if LAST_MESSAGE_NUDGE_TEXT not in nudge_content:
                nudge_content = (nudge_content + "\n\n" + LAST_MESSAGE_NUDGE_TEXT).strip()
                await queue.put({"event": "token.delta", "data": {"text": "\n\n" + LAST_MESSAGE_NUDGE_TEXT}})
            messages = state.get("messages", [])
            for i in range(len(messages) - 1, -1, -1):
                msg = messages[i]
                if msg.get("role") == "assistant":
                    messages[i] = {"role": "assistant", "content": nudge_content}
                    break
            state["messages"] = messages

        payload = _wrap(nudge_content, next_count, self.max_messages)
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
