from __future__ import annotations

import logging
import os
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessageChunk
from langfuse.callback import CallbackHandler
from langgraph.graph.state import CompiledStateGraph

from app.core.app_state import (
    get_sse_queue,
    get_supervisor_graph,
    get_last_emitted_text,
    set_last_emitted_text,
)
from app.repositories.session_store import InMemorySessionStore, get_session_store
from app.utils.welcome import generate_personalized_welcome

langfuse_handler = CallbackHandler(
    public_key=os.getenv("LANGFUSE_PUBLIC_SUPERVISOR_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_SUPERVISOR_KEY"),
    host=os.getenv("LANGFUSE_HOST_SUPERVISOR"),
)

logger = logging.getLogger(__name__)

logger.info(
    f"Langfuse env vars: {os.getenv('LANGFUSE_PUBLIC_SUPERVISOR_KEY')}, "
    f"{os.getenv('LANGFUSE_SECRET_SUPERVISOR_KEY')}, {os.getenv('LANGFUSE_HOST_SUPERVISOR')}"
)


# Warn if Langfuse env is missing so callbacks would be disabled silently
if not (
    os.getenv("LANGFUSE_PUBLIC_SUPERVISOR_KEY")
    and os.getenv("LANGFUSE_SECRET_SUPERVISOR_KEY")
    and os.getenv("LANGFUSE_HOST_SUPERVISOR")
):
    logger.warning(
        "Langfuse env vars missing or incomplete; callback tracing will be disabled"
    )

class SupervisorService:
    def _is_guardrail_intervention(self, text: str) -> bool:
        if not isinstance(text, str):
            return False
        low = text.lower()
        return (
            "guardrail_intervened" in low
            or "gr_input_blocked" in low
            or ("guardrail" in low and ("blocked" in low or "intervened" in low))
        )

    def _strip_guardrail_marker(self, text: str) -> str:
        if not isinstance(text, str):
            return ""
        start = text.find("[GUARDRAIL_INTERVENED]")
        if start != -1:
            return text[:start].rstrip()
        return text
    def _content_to_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        maybe_content = getattr(value, "content", None)
        if isinstance(maybe_content, (str, list)):
            return self._content_to_text(maybe_content)
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                if isinstance(item, dict):
                    text = item.get("text") or item.get("content") or ""
                    if isinstance(text, str):
                        parts.append(text)
                elif hasattr(item, "content"):
                    part_text = self._content_to_text(getattr(item, "content"))
                    if part_text:
                        parts.append(part_text)
            return "".join(parts)
        return ""
    async def initialize(self, *, user_id: str) -> dict[str, Any]:
        thread_id = str(uuid4())
        queue = get_sse_queue(thread_id)

        await queue.put({"event": "conversation.started", "data": {"thread_id": thread_id}})

        # Seed a minimal user context for personalization (extend with real fetch later)
        user_context = {
            "identity": {"preferred_name": "Alex"},
            "locale": "en-US",
            "tone": "clear",
            "goals": ["save more", "reduce debt"],
        }
        session_store = get_session_store()
        await session_store.set_session(
            thread_id,
            {
                "user_id": user_id,
                "user_context": user_context,
            },
        )

        welcome = await generate_personalized_welcome(user_context)
        await queue.put({"event": "token.delta", "data": {"text": welcome}})

        return {"thread_id": thread_id, "welcome": welcome, "sse_url": f"/supervisor/sse/{thread_id}"}

    async def process_message(self, *, thread_id: str, text: str) -> None:
        if not text or not text.strip():
            raise ValueError("Message text must not be empty")

        q = get_sse_queue(thread_id)
        await q.put({"event": "step.update", "data": {"status": "processing"}})

        graph: CompiledStateGraph = get_supervisor_graph()
        session_store: InMemorySessionStore = get_session_store()
        session_ctx = await session_store.get_session(thread_id) or {}
        configurable = {
            "thread_id": thread_id,
            "session_id": thread_id,
            **session_ctx,
        }

        async for event in graph.astream_events(
            {"messages": [{"role": "user", "content": text}]},
            version="v2",
            config={
                "callbacks": [langfuse_handler],
                "configurable": configurable,
            },
            stream_mode="values",
        ):
            name = event.get("name")
            etype = event.get("event")
            data = event.get("data") or {}

            if etype == "on_chat_model_stream":
                chunk = data.get("chunk")
                out = self._content_to_text(chunk)
                if out:
                    out = self._strip_guardrail_marker(out)
                if out:
                    last = get_last_emitted_text(thread_id)
                    if out != last:
                        await q.put({"event": "token.delta", "data": {"text": out}})
                        set_last_emitted_text(thread_id, out)
            elif etype == "on_tool_start":
                if name:
                    await q.put({"event": "tool.start", "data": {"tool": name}})
            elif etype == "on_tool_end":
                if name:
                    await q.put({"event": "tool.end", "data": {"tool": name}})
            elif etype == "on_chain_end":
                try:
                    output = data.get("output", {})
                    if isinstance(output, dict):
                        messages = output.get("messages")
                        if isinstance(messages, list) and messages:
                            last = messages[-1]
                            content_obj = (
                                last.get("content") if isinstance(last, dict) else getattr(last, "content", None)
                            )
                            text = self._content_to_text(content_obj)
                            if text:
                                text = self._strip_guardrail_marker(text)
                            if text:
                                last = get_last_emitted_text(thread_id)
                                if text != last:
                                    await q.put({"event": "token.delta", "data": {"text": text}})
                                    set_last_emitted_text(thread_id, text)
                except Exception:
                    pass

        await q.put({"event": "step.update", "data": {"status": "presented"}})


supervisor_service = SupervisorService()


