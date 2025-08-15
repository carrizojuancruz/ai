from __future__ import annotations

from typing import Any
from uuid import uuid4
import logging
import os
from langchain_core.messages import AIMessageChunk

from app.core.app_state import get_sse_queue, get_supervisor_graph
from app.repositories.session_store import get_session_store
from app.utils.welcome import generate_personalized_welcome
from langfuse.callback import CallbackHandler

langfuse_handler = CallbackHandler(
    public_key=os.getenv("LANGFUSE_PUBLIC_SUPERVISOR_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_SUPERVISOR_KEY"),
    host=os.getenv("LANGFUSE_HOST_SUPERVISOR"),
)

logger = logging.getLogger(__name__)

logger.info(f"Langfuse env vars: {os.getenv('LANGFUSE_PUBLIC_SUPERVISOR_KEY')}, {os.getenv('LANGFUSE_SECRET_SUPERVISOR_KEY')}, {os.getenv('LANGFUSE_HOST_SUPERVISOR')}")


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

        graph = get_supervisor_graph()
        session_store = get_session_store()
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
                out: str | None = None
                if isinstance(chunk, AIMessageChunk):
                    out = chunk.content if isinstance(chunk.content, str) else None
                elif isinstance(chunk, dict):
                    maybe = chunk.get("content")
                    out = maybe if isinstance(maybe, str) else None
                if out:
                    await q.put({"event": "token.delta", "data": {"text": out}})
            elif etype == "on_tool_start":
                if name:
                    await q.put({"event": "tool.start", "data": {"tool": name}})
            elif etype == "on_tool_end":
                if name:
                    await q.put({"event": "tool.end", "data": {"tool": name}})
            elif etype == "on_chain_end" and name in {"research_agent", "math_agent", "supervisor"}:
                try:
                    output = data.get("output", {})
                    if isinstance(output, dict):
                        messages = output.get("messages")
                        if isinstance(messages, list) and messages:
                            last = messages[-1]
                            content = last.get("content") if isinstance(last, dict) else None
                            if isinstance(content, str) and content.strip():
                                await q.put({"event": "token.delta", "data": {"text": content}})
                except Exception:
                    pass

        await q.put({"event": "step.update", "data": {"status": "presented"}})


supervisor_service = SupervisorService()


