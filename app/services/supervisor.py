from __future__ import annotations

import json
import logging
import os
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
from app.models.user import UserContext
from app.repositories.session_store import InMemorySessionStore, get_session_store
from app.utils.welcome import call_llm, generate_personalized_welcome

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


def _find_latest_prior_thread(session_store: InMemorySessionStore, user_id: str, exclude_thread_id: str) -> Optional[str]:
    """Find the most recent previous thread for this user (excluding current thread)."""
    latest_thread = None
    latest_timestamp = None

    for thread_id, session_data in session_store.sessions.items():
        if thread_id == exclude_thread_id:
            continue

        if session_data.get("user_id") == user_id:
            timestamp = session_data.get("last_accessed")
            if timestamp and (latest_timestamp is None or timestamp > latest_timestamp):
                latest_thread = thread_id
                latest_timestamp = timestamp

    return latest_thread


def _load_conversation_messages(session_store: InMemorySessionStore, thread_id: str) -> List[Dict[str, str]]:
    """Load conversation messages from a thread's session data."""
    session_data = session_store.sessions.get(thread_id, {})
    return session_data.get("conversation_messages", [])


def _extract_chat_pairs(messages: List[Dict[str, str]]) -> List[Tuple[str, str]]:
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


async def _summarize_conversation(pairs: List[Tuple[str, str]]) -> Optional[str]:
    """Summarize a conversation into a short paragraph (<= 500 chars)."""
    if not pairs:
        return None

    # Build transcript (limit to prevent token overflow)
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


async def _get_prior_conversation_summary(session_store: InMemorySessionStore, user_id: str, current_thread_id: str) -> Optional[str]:
    """Get summary of the most recent prior conversation for this user."""
    try:
        # Find the latest previous thread for this user
        prior_thread_id = _find_latest_prior_thread(session_store, user_id, current_thread_id)

        if not prior_thread_id:
            logger.info(f"No prior conversation found for user {user_id}")
            return None

        # Load messages from that thread
        messages = _load_conversation_messages(session_store, prior_thread_id)

        if not messages:
            logger.info(f"No messages found in prior thread {prior_thread_id} for user {user_id}")
            return None

        # Extract chat pairs and summarize
        chat_pairs = _extract_chat_pairs(messages)

        if not chat_pairs:
            logger.info(f"No valid chat pairs found in prior thread {prior_thread_id} for user {user_id}")
            return None

        summary = await _summarize_conversation(chat_pairs)

        logger.info(f"Generated prior summary for user {user_id}: {len(summary or '')} chars")
        return summary

    except Exception as e:
        logger.exception(f"Error getting prior conversation summary for user {user_id}: {e}")
        return None


class SupervisorService:
    async def _load_user_context_from_external(self, user_id: UUID) -> UserContext:
        """Load UserContext from external FOS service with fallback."""
        try:
            from app.services.external_context.client import ExternalUserRepository
            from app.services.external_context.mapping import map_ai_context_to_user_context

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
            from app.services.external_context.client import ExternalUserRepository
            from app.services.external_context.mapping import map_user_context_to_ai_context

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
            logger.warning(f"[SUPERVISOR] Failed to export user context: {e}")
            return False

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
    async def initialize(self, *, user_id: UUID) -> dict[str, Any]:
        thread_id = str(uuid4())
        queue = get_sse_queue(thread_id)

        await queue.put({"event": "conversation.started", "data": {"thread_id": thread_id}})

        # Load UserContext from external FOS service
        session_store = get_session_store()
        uid: UUID = user_id
        ctx = await self._load_user_context_from_external(uid)

        await session_store.set_session(
            thread_id,
            {
                "user_id": str(uid),
                "user_context": ctx.model_dump(mode="json"),
                "conversation_messages": [],  # Initialize empty message history
            },
        )

        # Get summary of prior conversation
        prior_summary = await _get_prior_conversation_summary(session_store, str(uid), thread_id)

        # Generate welcome message with prior conversation context
        user_context = (await session_store.get_session(thread_id) or {}).get("user_context", {})
        welcome = await generate_personalized_welcome(user_context, prior_summary)
        await queue.put({"event": "token.delta", "data": {"text": welcome}})

        logger.info(f"Initialize complete for user {uid}: thread={thread_id}, has_prior_summary={bool(prior_summary)}")

        return {
            "thread_id": thread_id,
            "welcome": welcome,
            "sse_url": f"/supervisor/sse/{thread_id}",
            "prior_conversation_summary": prior_summary
        }

    async def process_message(self, *, thread_id: str, text: str) -> None:
        if not text or not text.strip():
            raise ValueError("Message text must not be empty")

        q = get_sse_queue(thread_id)
        await q.put({"event": "step.update", "data": {"status": "processing"}})

        graph: CompiledStateGraph = get_supervisor_graph()
        session_store: InMemorySessionStore = get_session_store()
        session_ctx = await session_store.get_session(thread_id) or {}

        # Store the user message
        conversation_messages = session_ctx.get("conversation_messages", [])
        conversation_messages.append({
            "role": "user",
            "content": text.strip()
        })
        # Collect assistant response
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
                if out and not self._is_injected_context(out):
                    last = get_last_emitted_text(thread_id)
                    if out != last:
                        await q.put({"event": "token.delta", "data": {"text": out}})
                        set_last_emitted_text(thread_id, out)
                        # Collect assistant response parts
                        assistant_response_parts.append(out)
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
                            if text and not self._is_injected_context(text):
                                last = get_last_emitted_text(thread_id)
                                if text != last:
                                    await q.put({"event": "token.delta", "data": {"text": text}})
                                    set_last_emitted_text(thread_id, text)
                                    # Collect final assistant response
                                    assistant_response_parts.append(text)
                except Exception:
                    pass

        await q.put({"event": "step.update", "data": {"status": "presented"}})

        # Store the complete conversation (user + assistant messages)
        try:
            if assistant_response_parts:
                # Combine all assistant response parts
                assistant_response = "".join(assistant_response_parts).strip()
                if assistant_response:
                    conversation_messages.append({
                        "role": "assistant",
                        "content": assistant_response
                    })

            # Update session with complete conversation
            session_ctx["conversation_messages"] = conversation_messages
            await session_store.set_session(thread_id, session_ctx)
            logger.info(f"Stored conversation for thread {thread_id}: {len(conversation_messages)} messages")

            # Export updated UserContext back to external FOS service
            user_id = session_ctx.get("user_id")
            if user_id:
                user_ctx_dict = session_ctx.get("user_context", {})
                if user_ctx_dict:
                    ctx = UserContext.model_validate(user_ctx_dict)
                    await self._export_user_context_to_external(ctx)

        except Exception as e:
            logger.exception(f"Failed to store conversation for thread {thread_id}: {e}")


supervisor_service = SupervisorService()


