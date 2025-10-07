from __future__ import annotations

import asyncio
import json
import logging
import re
from os import environ
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from langfuse.callback import CallbackHandler
from langgraph.graph.state import CompiledStateGraph

from app.agents.supervisor.i18n import (
    _get_random_budget_completed,
    _get_random_budget_current,
    _get_random_finance_completed,
    _get_random_finance_current,
    _get_random_step_planning_completed,
    _get_random_step_planning_current,
    _get_random_wealth_completed,
    _get_random_wealth_current,
)
from app.core.app_state import (
    get_sse_queue,
    get_supervisor_graph,
)
from app.core.config import config
from app.models.user import UserContext
from app.repositories.database_service import get_database_service
from app.repositories.session_store import InMemorySessionStore, get_session_store
from app.services.external_context.user.mapping import map_ai_context_to_user_context
from app.services.external_context.user.repository import ExternalUserRepository
from app.services.utils import get_blocked_topics
from app.utils.mapping import get_source_name
from app.utils.tools import check_repeated_sources
from app.utils.welcome import call_llm, generate_personalized_welcome

environ["LANGFUSE_TRACING_ENVIRONMENT"] = config.LANGFUSE_TRACING_ENVIRONMENT

langfuse_handler = CallbackHandler(
    public_key=config.LANGFUSE_PUBLIC_SUPERVISOR_KEY,
    secret_key=config.LANGFUSE_SECRET_SUPERVISOR_KEY,
    host=config.LANGFUSE_HOST_SUPERVISOR,
)

logger = logging.getLogger(__name__)

STREAM_WORD_GROUP_SIZE = 3



# Guardrail handling
GUARDRAIL_INTERVENED_MARKER: str = "[GUARDRAIL_INTERVENED]"
GUARDRAIL_USER_PLACEHOLDER: str = "THIS MESSAGE HIT THE BEDROCK GUARDRAIL, SO IT WAS REMOVED"

_EMOJI_STRIP_RE = re.compile(
    r"[\U0001F300-\U0001FAFF\u2600-\u26FF\u2700-\u27BF\U0001F1E6-\U0001F1FF\U0001F3FB-\U0001F3FF\u200D\uFE0F\u20E3\u2066-\u2069]+",
    flags=re.UNICODE,
)

def _strip_emojis(text: str) -> str:
    if not isinstance(text, str):
        return text
    return _EMOJI_STRIP_RE.sub("", text)

# Warn if Langfuse env is missing so callbacks would be disabled silently
if not config.is_langfuse_supervisor_enabled():
    logger.warning("Langfuse env vars missing or incomplete; callback tracing will be disabled")


class SupervisorService:
    def _has_guardrail_intervention(self, text: str) -> bool:
        if not isinstance(text, str):
            return False
        return GUARDRAIL_INTERVENED_MARKER in text

    async def _load_user_context_from_external(self, user_id: UUID) -> UserContext:
        """Load UserContext from external FOS service with fallback."""
        try:
            repo = ExternalUserRepository()
            external_ctx = await repo.get_by_id(user_id)

            ctx = UserContext(user_id=user_id)
            ctx.blocked_topics = await get_blocked_topics(user_id)
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

    def _strip_guardrail_marker(self, text: str) -> str:
        if not isinstance(text, str):
            return ""
        start = text.find(GUARDRAIL_INTERVENED_MARKER)
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

    def _add_source_from_tool_end(
        self, sources: list[dict[str, Any]], name: str, data: dict[str, Any], current_agent: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Add the source to the sources list from the tool end event.

        Args:
            sources: Current list of sources
            name: Tool name
            data: Tool output data
            current_agent: Currently active agent (e.g., 'transfer_to_finance_agent')

        """
        if current_agent in ["transfer_to_finance_agent", "transfer_to_goal_agent"]:
            return sources

        if name == "search_kb":
            return sources

        if "output" not in data:
            return sources

        output = data["output"]

        if hasattr(output, "__class__") and "coroutine" in str(output.__class__).lower():
            logger.warning(f"[SUPERVISOR] Tool {name} returned unawaited coroutine: {output}")
            return sources

        content = (
            output.content
            if hasattr(output, "content")
            else output.get("content", output)
            if isinstance(output, dict)
            else output
        )

        if hasattr(content, "__class__") and "coroutine" in str(content.__class__).lower():
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

        items = (
            content
            if isinstance(content, list)
            else [content]
            if isinstance(content, dict) and "source" in content
            else []
        )

        sources_added = 0
        for item in items:
            if not isinstance(item, dict) or "source" not in item:
                continue

            source_content = item["source"]
            if (
                not source_content
                or not isinstance(source_content, str)
                or "coroutine" in str(type(source_content)).lower()
            ):
                continue

            new_source = {"name": get_source_name(name), "url": source_content}

            metadata = item.get("metadata", {})
            if isinstance(metadata, dict):
                for key, meta_key in [
                    ("name", "source_name"),
                    ("type", "type"),
                    ("category", "category"),
                    ("description", "description"),
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
            "Use first-person perspective consistently. "
            "Focus on key topics, decisions, and memorable moments. "
            "Keep it under 500 characters. Return ONLY the summary paragraph, no extra text. "
            "IMPORTANT: Always maintain consistent narrative perspective - refer to Vera as 'I' (subject) or 'me' (object) "
            "and the user as 'You'. Use 'we' when appropriate. Keep the same perspective throughout the summary."
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

        has_financial_accounts = False
        try:
            db_service = get_database_service()
            async with db_service.get_session() as session:
                repo = db_service.get_finance_repository(session)
                has_financial_accounts = await repo.user_has_any_accounts(uid)
        except Exception as e:
            logger.warning(f"[SUPERVISOR] Failed to check financial accounts for user {uid}: {e}")

        logger.info(f"[SUPERVISOR] User {uid} has financial accounts: {has_financial_accounts}")
        await session_store.set_session(
            thread_id,
            {
                "user_id": str(uid),
                "user_context": ctx.model_dump(mode="json"),
                "conversation_messages": [],
                "has_financial_accounts": has_financial_accounts,
            },
        )

        prior_summary = await self._get_prior_conversation_summary(session_store, str(uid), thread_id)

        logger.info(f"[SUPERVISOR] Generating welcome message with icebreaker support for user {uid}")

        icebreaker_used: bool = False
        icebreaker_hint: str | None = None
        try:
            from app.services.nudges.icebreaker_processor import get_icebreaker_processor

            processor = get_icebreaker_processor()
            logger.info(f"Getting icebreaker via FOS API for user {uid}")
            raw_icebreaker = await processor.process_icebreaker_for_user(uid)
            logger.info(f"Finished getting icebreaker via FOS API for user {uid}")
            if raw_icebreaker and raw_icebreaker.strip():
                icebreaker_hint = raw_icebreaker.strip()
                icebreaker_used = True
                logger.info(f"[SUPERVISOR] Icebreaker hint captured for user {uid}")
        except Exception as e:
            logger.warning(f"[SUPERVISOR] Icebreaker polling failed for user {uid}: {e}")

        user_ctx_for_welcome = (await session_store.get_session(thread_id) or {}).get("user_context", {})
        welcome = await generate_personalized_welcome(user_ctx_for_welcome, prior_summary, icebreaker_hint)

        logger.info(
            f"Initialize complete for user {uid}: thread={thread_id}, has_prior_summary={bool(prior_summary)}, icebreaker_used={icebreaker_used}"
        )

        await queue.put({"event": "message.completed", "data": {"text": welcome}})

        if has_financial_accounts:
            try:
                import asyncio

                from app.core.app_state import get_finance_agent

                fa = get_finance_agent()
                asyncio.create_task(fa._fetch_shallow_samples(uid))
            except Exception:
                pass

        return {
            "thread_id": thread_id,
            "welcome": welcome,
            "sse_url": f"/supervisor/sse/{thread_id}",
            "prior_conversation_summary": prior_summary,
        }

    async def process_message(self, *, thread_id: str, text: str) -> None:
        if not text or not text.strip():
            raise ValueError("Message text must not be empty")

        q = get_sse_queue(thread_id)
        current_description = _get_random_step_planning_current()
        await q.put({"event": "step.update", "data": {"status": "processing", "description": current_description}})

        graph: CompiledStateGraph = get_supervisor_graph()
        session_store: InMemorySessionStore = get_session_store()
        session_ctx = await session_store.get_session(thread_id) or {}
        sources = []

        conversation_messages = session_ctx.get("conversation_messages", [])
        conversation_messages.append({"role": "user", "content": text.strip(), "sources": sources})

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

        emitted_handoff_back_keys: set[str] = set()
        current_agent_tool: Optional[str] = None
        active_handoffs: set[str] = set()

        latest_response_text: Optional[str] = None
        supervisor_latest_response_text: Optional[str] = None
        response_event_count = 0
        seen_responses: set[int] = set()
        streamed_responses: set[str] = set()
        hit_guardrail: bool = False

        metadata: dict[str, str] = {"langfuse_session_id": thread_id}
        if user_id:
            metadata["langfuse_user_id"] = str(user_id)

        config_payload: dict[str, Any] = {
            "callbacks": [langfuse_handler],
            "configurable": configurable,
            "thread_id": thread_id,
        }
        if metadata:
            config_payload["metadata"] = metadata

        async for event in graph.astream_events(
            {
                "messages": [{"role": "user", "content": text}],
                "sources": sources,
                "context": {"thread_id": thread_id},
            },
            version="v2",
            config=config_payload,
            stream_mode="values",
            subgraphs=True,
        ):
            name = event.get("name")
            etype = event.get("event")
            data = event.get("data") or {}

            response_text = ""
            try:
                if data and 'output' in data and 'messages' in data['output']:
                    messages_supervisor = data['output']['messages']
                    for msg in reversed(messages_supervisor):
                        content_list = getattr(msg, 'content', None)
                        if isinstance(content_list, list):
                            for content_item in reversed(content_list):
                                if isinstance(content_item, dict) and content_item.get('type') == 'text':
                                    candidate = content_item.get('text', '')
                                    if candidate and candidate.strip():
                                        response_text = candidate
                                        break
                        if response_text:
                            break

                # Quick fix: Update latest response from any event
                if response_text:
                    prev_latest = (latest_response_text[:80] + "...") if latest_response_text else None
                    latest_response_text = response_text
                    # If this update is from supervisor, also update the supervisor buffer
                    if name == "supervisor":
                        prev_super = (supervisor_latest_response_text[:80] + "...") if supervisor_latest_response_text else None
                        supervisor_latest_response_text = response_text
                        logger.info(
                            f"[TRACE] supervisor.buffer.update from={prev_super} to={(supervisor_latest_response_text[:80] + '...') if supervisor_latest_response_text else None}"
                        )
                    response_event_count += 1
                    logger.info(
                        f"[TRACE] latest.update event={name} type={etype} count={response_event_count} "
                        f"from={prev_latest} to={(latest_response_text[:80] + '...') if latest_response_text else None}"
                    )

            except: # noqa: E722
                pass




            if etype == "on_tool_start":
                tool_name = name
                if tool_name and tool_name.startswith("transfer_to_"):
                    current_agent_tool = tool_name
                    active_handoffs.add(tool_name)
                    # Clear global buffer to prevent accidental fallback streaming during handoff
                    latest_response_text = None

                    description = "Consulting a source"
                    if tool_name == "transfer_to_finance_agent":
                        description = _get_random_finance_current()
                    elif tool_name == "transfer_to_goal_agent":
                        description = _get_random_budget_current()
                    elif tool_name == "transfer_to_wealth_agent":
                        description = _get_random_wealth_current()

                    await q.put(
                        {
                            "event": "source.search.start",
                            "data": {
                                "tool": tool_name,
                                "source": tool_name.replace("transfer_to_", "").replace("_", " ").title(),
                                "description": description,
                            },
                        }
                    )
                    continue

                if name and not name.startswith("transfer_to_"):
                    await q.put({"event": "tool.start", "data": {"tool": name}})


            elif etype == "on_tool_end":
                sources = self._add_source_from_tool_end(sources, name, data, current_agent_tool)
                if name and not name.startswith("transfer_to_"):
                    await q.put({"event": "tool.end", "data": {"tool": name}})
            elif etype == "on_chain_end":
                try:
                    output = data.get("output", {})
                    if isinstance(output, dict):
                        if "sources" in output and output["sources"]:
                            handoff_sources = output["sources"]
                            if handoff_sources:
                                sources.extend(handoff_sources)
                                logger.info(f"[TRACE] supervisor.handoff.sources_added count={len(handoff_sources)}")

                        messages = output.get("messages")
                        if isinstance(messages, list) and messages:
                            def _meta(msg):
                                try:
                                    if isinstance(msg, dict):
                                        return (msg.get("response_metadata", {}) or {})
                                    return getattr(msg, "response_metadata", {}) or {}
                                except Exception:
                                    return {}

                            last_tool = next(
                                (m for m in messages if (_meta(m).get("is_handoff_back", False))),
                                None,
                            )
                            if last_tool:
                                agent_name: str = getattr(last_tool, "name", None) or "unknown_agent"
                                # Create a more robust dedupe key using agent name and current tool
                                back_tool = "transfer_back_to_supervisor"  # Standard back tool name
                                dedupe_key = f"{agent_name}:{current_agent_tool or 'unknown'}"

                                # Only emit source.search.end if we have an active handoff to close
                                if (dedupe_key not in emitted_handoff_back_keys and
                                    current_agent_tool and
                                    current_agent_tool in active_handoffs):

                                    emitted_handoff_back_keys.add(dedupe_key)
                                    # Remove from active handoffs since we're closing it
                                    active_handoffs.discard(current_agent_tool)

                                    description = "Returned from source"  # fallback
                                    if current_agent_tool == "transfer_to_finance_agent":
                                        description = _get_random_finance_completed()
                                    elif current_agent_tool == "transfer_to_goal_agent":
                                        description = _get_random_budget_completed()
                                    elif current_agent_tool == "transfer_to_wealth_agent":
                                        description = _get_random_wealth_completed()

                                    supervisor_name = "Supervisor"
                                    await q.put(
                                        {
                                            "event": "source.search.end",
                                            "data": {
                                                "tool": back_tool,
                                                "source": supervisor_name,
                                                "description": description,
                                            },
                                        }
                                    )
                                    current_agent_tool = None
                except Exception as e:
                    logger.info(f"[TRACE] chain_end.handoff_close.error err={e}")

                # Stream only when supervisor has authored text and no active handoff is open
                if name == "supervisor" and supervisor_latest_response_text and not active_handoffs:
                    text_to_stream = supervisor_latest_response_text or ""
                    # Detect and clean guardrail marker for streaming
                    hit_guardrail = hit_guardrail or self._has_guardrail_intervention(text_to_stream)
                    text_to_stream_cleaned = _strip_emojis(self._strip_guardrail_marker(text_to_stream))
                    # Check if we've already streamed this exact response text (prevents duplicate streaming after handoffs)
                    response_text_normalized = text_to_stream_cleaned.strip()
                    if response_text_normalized in streamed_responses:
                        logger.info("[TRACE] supervisor.stream.skip reason=exact_text_duplicate")
                        continue

                    response_hash = hash(response_text_normalized)
                    if response_hash in seen_responses:
                        logger.info("[TRACE] supervisor.stream.skip reason=hash_duplicate")
                        continue

                    logger.info("[TRACE] supervisor.stream.start")
                    seen_responses.add(response_hash)
                    streamed_responses.add(response_text_normalized)
                    words = text_to_stream_cleaned.split(" ")
                    chunks_emitted = 0
                    for i in range(0, len(words), STREAM_WORD_GROUP_SIZE):
                        word_group = " ".join(words[i:i+STREAM_WORD_GROUP_SIZE])
                        if word_group.strip():
                            await q.put({"event": "token.delta", "data": {"text": word_group + " ", "sources": sources}})
                            chunks_emitted += 1
                            await asyncio.sleep(0)
                    logger.info(f"[TRACE] supervisor.stream.end chunks={chunks_emitted}")

        try:
            final_text = supervisor_latest_response_text
            if final_text:
                final_text_to_emit = _strip_emojis(self._strip_guardrail_marker(final_text) if hit_guardrail else final_text)
                await q.put({"event": "message.completed", "data": {"content": final_text_to_emit}})
        except Exception as e:
            logger.error(f"[DEBUG] Error sending message.completed: {e}")

        completed_description = _get_random_step_planning_completed()
        await q.put({"event": "step.update", "data": {"status": "presented", "description": completed_description}})

        try:
            final_text = supervisor_latest_response_text
            if final_text:
                assistant_response = _strip_emojis(self._strip_guardrail_marker(final_text) if hit_guardrail else final_text).strip()
                if hit_guardrail:
                    # Replace the last user message with a guardrail placeholder to prevent loops
                    for i in range(len(conversation_messages) - 1, -1, -1):
                        msg = conversation_messages[i]
                        if isinstance(msg, dict) and msg.get("role") == "user":
                            msg["content"] = GUARDRAIL_USER_PLACEHOLDER
                            break
                if assistant_response:
                    conversation_messages.append(
                        {"role": "assistant", "content": assistant_response, "sources": sources}
                    )

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
