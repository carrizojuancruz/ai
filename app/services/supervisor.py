from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
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
from app.models.user import UserContext
from app.repositories.database_service import get_database_service
from app.repositories.session_store import InMemorySessionStore, get_session_store
from app.utils.mapping import get_source_name
from app.utils.tools import check_repeated_sources
from app.utils.welcome import call_llm, generate_personalized_welcome

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
    logger.warning("Langfuse env vars missing or incomplete; callback tracing will be disabled")


class SupervisorService:
    async def _load_user_context_from_external(self, user_id: UUID) -> UserContext:
        """Load UserContext from external FOS service with fallback."""
        try:
            from app.services.external_context.user.mapping import map_ai_context_to_user_context
            from app.services.external_context.user.repository import ExternalUserRepository

            repo = ExternalUserRepository()
            external_ctx = await repo.get_by_id(user_id)

            ctx = UserContext(user_id=user_id)
            if external_ctx:
                ctx = map_ai_context_to_user_context(external_ctx, ctx)
                logger.info(f"[SUPERVISOR] External AI Context loaded for user: {user_id}")
            else:
                logger.info(f"[SUPERVISOR] No external AI Context found for user: {user_id}")

            return ctx

        except Exception as e:
            logger.warning(f"[SUPERVISOR] Failed to load external user context: {e}")
            # Fallback to empty UserContext if external service fails
            return UserContext(user_id=user_id)

    async def _export_user_context_to_external(self, user_context: UserContext) -> bool:
        """Export UserContext to external FOS service."""
        try:
            from app.services.external_context.user.mapping import map_user_context_to_ai_context
            from app.services.external_context.user.repository import ExternalUserRepository

            repo = ExternalUserRepository()
            body = map_user_context_to_ai_context(user_context)
            logger.info(f"[SUPERVISOR] Prepared external payload: {json.dumps(body, ensure_ascii=False)}")
            resp = await repo.upsert(user_context.user_id, body)
            if resp is not None:
                logger.info(f"[SUPERVISOR] External API acknowledged update for user {user_context.user_id}")
                return True
            else:
                logger.warning(f"[SUPERVISOR] External API returned no body or 404 for user {user_context.user_id}")
                return False
        except Exception as e:
            logger.error(f"[SUPERVISOR] Failed to export user context: {e}")
            return False

    async def _get_user_context_from_db(self, user_id: UUID) -> UserContext | None:
        """Get user context from database using the centralized database service."""
        try:
            db_service = get_database_service()
            async with db_service.get_session() as session:
                repo = db_service.get_user_repository(session)
                return await repo.get_by_id(user_id)
        except Exception as e:
            logger.error(f"[SUPERVISOR] Failed to load user context from database: {e}")
            return None

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
        return t.startswith("CONTEXT_PROFILE:") or t.startswith("Relevant context for tailoring this turn:")

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

    def _add_source_from_tool_end(self, sources: list[dict[str, Any]], name: str, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Add the source to the sources list from the tool end event."""
        if "output" not in data:
            return sources

        output = data["output"]

        if hasattr(output, '__class__') and 'coroutine' in str(output.__class__).lower():
            logger.warning(f"[SUPERVISOR] Tool {name} returned unawaited coroutine: {output}")
            return sources

        content = output.content if hasattr(output, "content") else output.get("content", output) if isinstance(output, dict) else output

        if hasattr(content, '__class__') and 'coroutine' in str(content.__class__).lower():
            logger.warning(f"[SUPERVISOR] Tool {name} content is unawaited coroutine: {content}")
            return sources

        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                if content.strip():
                    new_source = {"name": get_source_name(name), "url": content}
                    if check_repeated_sources(sources, new_source):
                        sources.append(new_source)
                return sources

        items = content if isinstance(content, list) else [content] if isinstance(content, dict) and "source" in content else []

        sources_added = 0
        for item in items:
            if not isinstance(item, dict) or "source" not in item:
                continue

            source_content = item["source"]
            if not source_content or not isinstance(source_content, str) or 'coroutine' in str(type(source_content)).lower():
                continue

            new_source = {
                "name": get_source_name(name),
                "url": source_content
            }

            metadata = item.get("metadata", {})
            if isinstance(metadata, dict):
                for key, meta_key in [
                    ("name", "source_name"),
                    ("type", "type"),
                    ("category", "category"),
                    ("description", "description")
                ]:
                    if metadata.get(key):
                        new_source[meta_key] = metadata[key]

            if check_repeated_sources(sources, new_source):
                sources.append(new_source)
                sources_added += 1

        if sources_added > 0:
            logger.info(f"[SUPERVISOR] Added {sources_added} sources from tool '{name}'")

        return sources

    async def _find_latest_prior_thread(
        self, session_store: InMemorySessionStore, user_id: str, exclude_thread_id: str
    ) -> Optional[str]:
        """Find the most recent previous thread for this user (excluding current thread)."""
        user_threads = await session_store.get_user_threads(user_id)

        latest_thread = None
        latest_timestamp = None

        for thread_id in user_threads:
            if thread_id == exclude_thread_id:
                continue

            session_data = session_store.sessions.get(thread_id, {})
            timestamp = session_data.get("last_accessed")
            if timestamp and (latest_timestamp is None or timestamp > latest_timestamp):
                latest_thread = thread_id
                latest_timestamp = timestamp

        return latest_thread

    def _load_conversation_messages(self, session_store: InMemorySessionStore, thread_id: str) -> List[Dict[str, str]]:
        """Load conversation messages from a thread's session data."""
        session_data = session_store.sessions.get(thread_id, {})
        return session_data.get("conversation_messages", [])

    def _extract_chat_pairs(self, messages: List[Dict[str, str]]) -> List[Tuple[str, str]]:
        """Extract (role, content) pairs from messages, keeping only user/assistant."""
        pairs = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "").strip()

            if role in ("user", "human") and content:
                pairs.append(("user", content))
            elif role in ("assistant", "ai") and content:
                pairs.append(("assistant", content))

        return pairs

    async def _summarize_conversation(self, pairs: List[Tuple[str, str]]) -> Optional[str]:
        """Summarize a conversation into a short paragraph (<= 500 chars)."""
        if not pairs:
            return None

        transcript_lines = []
        total_chars = 0
        max_chars = 3000

        for role, content in pairs:
            line = f"{role.title()}: {content}"
            if total_chars + len(line) + 1 > max_chars:
                break
            transcript_lines.append(line)
            total_chars += len(line) + 1

        if not transcript_lines:
            return None

        transcript = "\n".join(transcript_lines)

        system_prompt = (
            "You are a helpful assistant summarizing past conversations. "
            "Write a natural, conversational summary as if you were catching up with an old friend. "
            "Use first-person perspective where appropriate. "
            "Focus on key topics, decisions, and memorable moments. "
            "Keep it under 500 characters. Return ONLY the summary paragraph, no extra text."
            "\n\nExamples:"
            "\n- We talked about your cat Luna being extra playful lately and how you're thinking about her birthday party."
            "\n- You mentioned trying that new vegan ramen recipe and we discussed some fun variations to try."
            "\n- We explored different hiking trails in Golden Gate Park and you shared your favorite spots."
            "\n- You were excited about the book club idea and we brainstormed some great title suggestions."
        )

        prompt = f"Past conversation:\n{transcript}\n\nNatural summary:"

        try:
            summary = await call_llm(system_prompt, prompt)
            if summary and summary.strip():
                return summary.strip()
        except Exception as e:
            logger.exception(f"Error summarizing conversation: {e}")

        return None

    async def _get_prior_conversation_summary(
        self, session_store: InMemorySessionStore, user_id: str, current_thread_id: str
    ) -> Optional[str]:
        """Get summary of the most recent prior conversation for this user."""
        try:
            prior_thread_id = await self._find_latest_prior_thread(session_store, user_id, current_thread_id)

            if not prior_thread_id:
                logger.info(f"No prior conversation found for user {user_id}")
                return None

            messages = self._load_conversation_messages(session_store, prior_thread_id)

            if not messages:
                logger.info(f"No messages found in prior thread {prior_thread_id} for user {user_id}")
                return None

            chat_pairs = self._extract_chat_pairs(messages)

            if not chat_pairs:
                logger.info(f"No valid chat pairs found in prior thread {prior_thread_id} for user {user_id}")
                return None

            summary = await self._summarize_conversation(chat_pairs)

            logger.info(f"Generated prior summary for user {user_id}: {len(summary or '')} chars")
            return summary

        except Exception as e:
            logger.exception(f"Error getting prior conversation summary for user {user_id}: {e}")
            return None

    async def initialize(self, *, user_id: UUID) -> dict[str, Any]:
        """Initialize the supervisor service."""
        thread_id = str(uuid4())
        queue = get_sse_queue(thread_id)

        await queue.put({"event": "conversation.started", "data": {"thread_id": thread_id}})

        session_store = get_session_store()
        uid: UUID = user_id
        ctx = await self._load_user_context_from_external(uid)

        await session_store.set_session(
            thread_id,
            {
                "user_id": str(uid),
                "user_context": ctx.model_dump(mode="json"),
                "conversation_messages": [],
            },
        )

        prior_summary = await self._get_prior_conversation_summary(session_store, str(uid), thread_id)

        user_context = (await session_store.get_session(thread_id) or {}).get("user_context", {})
        welcome = await generate_personalized_welcome(user_context, prior_summary)
        await queue.put({"event": "token.delta", "data": {"text": welcome}})

        logger.info(f"Initialize complete for user {uid}: thread={thread_id}, has_prior_summary={bool(prior_summary)}")

        await queue.put({"event": "message.completed", "data": {"text": welcome}})

        try:
            import asyncio

            from app.agents.supervisor.finance_agent.agent import _finance_agent
            asyncio.create_task(_finance_agent._fetch_shallow_samples(uid))
        except Exception:
            pass

        return {
            "thread_id": thread_id,
            "welcome": welcome,
            "sse_url": f"/supervisor/sse/{thread_id}",
            "prior_conversation_summary": prior_summary,
        }

    async def initialize_nudge(
        self, *, user_id: UUID, nudge_prompt_line: str, preview_text: str, channel: str = "push"
    ) -> dict[str, Any]:
        thread_id = str(uuid4())
        queue = get_sse_queue(thread_id)

        await queue.put({"event": "conversation.started", "data": {"thread_id": thread_id, "nudge": True}})

        session_store = get_session_store()
        uid: UUID = user_id
        ctx = await self._load_user_context_from_external(uid)

        prior_summary = await self._get_prior_conversation_summary(session_store, str(uid), thread_id)

        user_context = ctx.model_dump(mode="json")

        system_prompt = (
            "You are Vera, a helpful and friendly AI assistant."
            "You're starting a proactive conversation based on something you've noticed."
            "Be warm, conversational, and supportive. Keep your opening concise and engaging."
        )

        prompt = f"Prior context: {prior_summary}\n\n{nudge_prompt_line}" if prior_summary else nudge_prompt_line

        try:
            nudge_message = await call_llm(system_prompt, prompt)

            if not nudge_message:
                nudge_message = f"Hi! {preview_text} Let me know if you'd like to discuss this."

        except Exception as e:
            logger.error(f"Failed to generate nudge message: {e}")
            nudge_message = f"Hi! {preview_text} Let me know if you'd like to discuss this."

        await session_store.set_session(
            thread_id,
            {
                "user_id": str(uid),
                "user_context": user_context,
                "conversation_messages": [{"role": "assistant", "content": nudge_message}],
                "nudge_metadata": {
                    "preview_text": preview_text,
                    "channel": channel,
                    "initialized_at": datetime.now(timezone.utc).isoformat(),
                },
            },
        )

        await queue.put(
            {
                "event": "nudge.initialized",
                "data": {"thread_id": thread_id, "message": nudge_message, "preview_text": preview_text},
            }
        )

        logger.info(f"Nudge initialized for user {uid}: thread={thread_id}, channel={channel}")

        return {
            "thread_id": thread_id,
            "message": nudge_message,
            "preview_text": preview_text,
            "sse_url": f"/supervisor/sse/{thread_id}",
        }

    async def process_message(self, *, thread_id: str, text: str) -> None:
        if not text or not text.strip():
            raise ValueError("Message text must not be empty")

        q = get_sse_queue(thread_id)
        await q.put({"event": "step.update", "data": {"status": "processing"}})

        graph: CompiledStateGraph = get_supervisor_graph()
        session_store: InMemorySessionStore = get_session_store()
        session_ctx = await session_store.get_session(thread_id) or {}
        sources = []

        conversation_messages = session_ctx.get("conversation_messages", [])
        conversation_messages.append({"role": "user", "content": text.strip(),
            "sources": sources})
        assistant_response_parts = []

                # Refresh UserContext from external FOS service each turn to avoid stale profile
        user_id = session_ctx.get("user_id")
        if user_id:
            uid = UUID(user_id)
            ctx = await self._load_user_context_from_external(uid)
            session_ctx["user_context"] = ctx.model_dump(mode="json")
            await session_store.set_session(thread_id, session_ctx)
        configurable = {
            "thread_id": thread_id,
            "session_id": thread_id,
            **session_ctx,
            "user_id": user_id,
        }

        final_text_candidate: Optional[str] = None

        async for event in graph.astream_events(
            {"messages": [{"role": "user", "content": text}], "sources": sources},
            version="v2",
            config={
                "callbacks": [langfuse_handler],
                "configurable": configurable,
                "thread_id": thread_id,
            },
            stream_mode="values",
            subgraphs=True,
        ):

            name = event.get("name")
            etype = event.get("event")
            data = event.get("data") or {}

            # Only stream events from the supervisor node to avoid showing subagent activity
            if name != "supervisor":
                continue

            if etype == "on_chat_model_stream":
                chunk = data.get("chunk")
                out = self._content_to_text(chunk)
                if out:
                    out = self._strip_guardrail_marker(out)
                if out and not self._is_injected_context(out):
                    last = get_last_emitted_text(thread_id)
                    if out != last:
                        if name not in ["tools"]:
                            await q.put({"event": "token.delta", "data": {"text": out, "sources": sources}})
                            set_last_emitted_text(thread_id, out)
                        assistant_response_parts.append(out)
            elif etype == "on_tool_start":
                if name:
                    await q.put({"event": "tool.start", "data": {"tool": name}})
            elif etype == "on_tool_end":
                sources = self._add_source_from_tool_end(sources, name, data)
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
                            if text and not self._is_injected_context(text):
                                last = get_last_emitted_text(thread_id)
                                if text != last:
                                    if name not in ["tools"]:
                                        await q.put({"event": "token.delta", "data": {"text": text, "sources": sources}})
                                        set_last_emitted_text(thread_id, text)
                                    assistant_response_parts.append(text)
                except Exception:
                    pass

        try:
            final_text = "".join(assistant_response_parts).strip() if assistant_response_parts else (final_text_candidate or "")
            if final_text:
                await q.put({"event": "message.completed", "data": {"content": final_text}})
        except Exception:
            pass

        await q.put({"event": "step.update", "data": {"status": "presented"}})

        try:
            if assistant_response_parts:
                assistant_response = "".join(assistant_response_parts).strip()
                if assistant_response:
                    conversation_messages.append({"role": "assistant", "content": assistant_response,
                        "sources": sources})

            session_ctx["conversation_messages"] = conversation_messages
            await session_store.set_session(thread_id, session_ctx)
            logger.info(f"Stored conversation for thread {thread_id}: {len(conversation_messages)} messages")

            user_id = session_ctx.get("user_id")
            if user_id:
                user_ctx_dict = session_ctx.get("user_context", {})
                if user_ctx_dict:
                    ctx = UserContext.model_validate(user_ctx_dict)
                    await self._export_user_context_to_external(ctx)

        except Exception as e:
            logger.exception(f"Failed to store conversation for thread {thread_id}: {e}")


supervisor_service = SupervisorService()
