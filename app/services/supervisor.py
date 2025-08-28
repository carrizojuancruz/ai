from __future__ import annotations

import logging
import json
from typing import Any, Optional
from uuid import UUID, uuid4

from langfuse.callback import CallbackHandler
from langgraph.graph.state import CompiledStateGraph

from app.core.app_state import (
    get_last_emitted_text,
    get_sse_queue,
    get_supervisor_graph,
    set_last_emitted_text,
)
from app.core.config import config
from app.db.session import get_async_session
from app.models.user import UserContext
from app.repositories.postgres.user_repository import PostgresUserRepository
from app.repositories.session_store import InMemorySessionStore, get_session_store
from app.utils.mapping import get_all_source_key_names, get_source_name
from app.utils.tools import check_repeated_sources, include_in_array
from app.utils.welcome import generate_personalized_welcome

langfuse_handler = CallbackHandler(
    public_key=config.LANGFUSE_PUBLIC_SUPERVISOR_KEY,
    secret_key=config.LANGFUSE_SECRET_SUPERVISOR_KEY,
    host=config.LANGFUSE_HOST_SUPERVISOR,
)

logger = logging.getLogger(__name__)

logger.info(
    f"Langfuse env vars: {config.LANGFUSE_PUBLIC_SUPERVISOR_KEY}, "
    f"{config.LANGFUSE_SECRET_SUPERVISOR_KEY}, {config.LANGFUSE_HOST_SUPERVISOR}"
)


# Warn if Langfuse env is missing so callbacks would be disabled silently
if not config.is_langfuse_supervisor_enabled():
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
    def _is_injected_context(self, text: str) -> bool:
        if not isinstance(text, str):
            return False
        t = text.strip()
        return (
            t.startswith("CONTEXT_PROFILE:")
            or t.startswith("Relevant context for tailoring this turn:")
        )
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
                    part_text = self._content_to_text(item.content)
                    if part_text:
                        parts.append(part_text)
            return "".join(parts)
        return ""

    def _get_memory_id(self, checkpoint_ns: Optional[str] = None) -> str:
        """
        Get the memory id from the sources
        """
        if checkpoint_ns:
            # Split with ":" and get the last part if it exists
            parts = checkpoint_ns.split(":")
            if len(parts) > 0:
                return parts[-1]
        return ""
    
    def _add_source_from_tool_end(self, sources: list[dict[str, Any]], name: str, data: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Add the source to the sources list from the tool end event
        """
        if "output" in data:
            output = data["output"]
            if hasattr(output, "content"):
                content = output.content
            elif isinstance(output, dict) and "content" in output:
                content = output["content"]
            else:
                content = output
            if isinstance(content, str):
                content = json.loads(content)
            for item in content:
                if "source" in item and len(item["source"]) > 0:
                    if check_repeated_sources(sources, {"name": get_source_name(name), "source": item["source"]}):
                        sources.append({"name": get_source_name(name), "source": item["source"]})
        return sources
    
    def _add_source(self, sources: list[dict[str, Any]], name: str, event: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Add the source to the sources list
        """
        if include_in_array(get_all_source_key_names(),name) and check_repeated_sources(sources, {"name": get_source_name(name), "source": ""}):
            sources.append({"name": get_source_name(name), "source": self._get_memory_id(event.get("metadata", {}).get("langgraph_checkpoint_ns"))})
        return sources

    async def initialize(self, *, user_id: UUID) -> dict[str, Any]:
        """
        Initialize the supervisor service
        """
        thread_id = str(uuid4())
        queue = get_sse_queue(thread_id)

        await queue.put({"event": "conversation.started", "data": {"thread_id": thread_id}})

        # Load or create UserContext from Postgres
        session_store = get_session_store()
        uid: UUID = user_id
        async for db in get_async_session():
            repo = PostgresUserRepository(db)
            ctx = await repo.get_by_id(uid)
            if ctx is None:
                ctx = UserContext(user_id=uid)
                ctx = await repo.upsert(ctx)
            await session_store.set_session(
                thread_id,
                {
                    "user_id": str(uid),
                    "user_context": ctx.model_dump(mode="json"),
                },
            )

        welcome = await generate_personalized_welcome((await session_store.get_session(thread_id) or {}).get("user_context", {}))
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
        # Refresh UserContext from Postgres each turn to avoid stale profile
        user_id = session_ctx.get("user_id")
        if user_id:
            try:
                uid = UUID(user_id)
                async for db in get_async_session():
                    repo = PostgresUserRepository(db)
                    ctx = await repo.get_by_id(uid)
                    if ctx is None:
                        ctx = UserContext(user_id=uid)
                        ctx = await repo.upsert(ctx)
                    session_ctx["user_context"] = ctx.model_dump(mode="json")
                    await session_store.set_session(thread_id, session_ctx)
            except Exception:
                pass
        configurable = {
            "thread_id": thread_id,
            "session_id": thread_id,
            **session_ctx,
        }
        sources = []

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
                if out and not self._is_injected_context(out):
                    last = get_last_emitted_text(thread_id)
                    if out != last:
                        await q.put({"event": "token.delta", "data": {"text": out, "sources": sources}})
                        set_last_emitted_text(thread_id, out)
            elif etype == "on_tool_start":
                if name:
                    await q.put({"event": "tool.start", "data": {"tool": name}})
            elif etype == "on_tool_end":
                sources = self._add_source_from_tool_end(sources, name, data)
                if name:
                    await q.put({"event": "tool.end", "data": {"tool": name}})
            elif etype == "on_chain_end":
                try:
                    sources = self._add_source(sources, name, event)
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
                            if text and not self._is_injected_context(text):
                                last = get_last_emitted_text(thread_id)
                                if text != last:
                                    await q.put({"event": "token.delta", "data": {"text": text, "sources": sources}})
                                    set_last_emitted_text(thread_id, text)
                except Exception:
                    pass

        await q.put({"event": "step.update", "data": {"status": "presented"}})


supervisor_service = SupervisorService()
