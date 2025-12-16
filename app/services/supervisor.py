from __future__ import annotations

import asyncio
import json
import logging
import re
from os import environ
from typing import Any, Awaitable, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from langfuse import Langfuse
from langfuse.langchain import CallbackHandler
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from app.agents.supervisor.finance_capture_agent.nova import generate_completion_response
from app.agents.supervisor.i18n import (
    _get_random_budget_completed,
    _get_random_budget_current,
    _get_random_finance_capture_completed,
    _get_random_finance_capture_current,
    _get_random_finance_completed,
    _get_random_finance_current,
    _get_random_step_planning_completed,
    _get_random_step_planning_current,
    _get_random_wealth_completed,
    _get_random_wealth_current,
)
from app.core.app_state import (
    get_audio_queue,
    get_sse_queue,
    get_supervisor_graph,
)
from app.core.config import config
from app.models.user import UserContext
from app.repositories.database_service import get_database_service
from app.repositories.session_store import InMemorySessionStore, get_session_store
from app.services.audio_service import get_audio_service, start_audio_service_for_thread
from app.services.external_context.user.mapping import (
    map_ai_context_to_user_context,
    map_user_context_to_ai_context,
)
from app.services.external_context.user.personal_information import PersonalInformationService
from app.services.external_context.user.profile_metadata import build_profile_metadata_payload
from app.services.external_context.user.repository import ExternalUserRepository
from app.services.llm.extended_description import (
    extract_agent_result_text,
    schedule_extended_description_update,
)
from app.services.location.normalizer import location_normalizer
from app.utils.mapping import get_source_name
from app.utils.tools import check_repeated_sources
from app.utils.welcome import call_llm, generate_personalized_welcome

environ["LANGFUSE_TRACING_ENVIRONMENT"] = config.LANGFUSE_TRACING_ENVIRONMENT

logger = logging.getLogger(__name__)

langfuse_handler = None
if config.LANGFUSE_PUBLIC_SUPERVISOR_KEY and config.LANGFUSE_SECRET_SUPERVISOR_KEY:
    try:
        Langfuse(
            public_key=config.LANGFUSE_PUBLIC_SUPERVISOR_KEY,
            secret_key=config.LANGFUSE_SECRET_SUPERVISOR_KEY,
            host=config.LANGFUSE_HOST,
        )
        langfuse_handler = CallbackHandler(public_key=config.LANGFUSE_PUBLIC_SUPERVISOR_KEY)
    except Exception as e:
        logger.warning("[Langfuse][supervisor] Failed to init callback handler: %s: %s", type(e).__name__, e)
        langfuse_handler = None

langfuse_goal_handler = None
if config.LANGFUSE_PUBLIC_GOAL_KEY and config.LANGFUSE_SECRET_GOAL_KEY:
    try:
        Langfuse(
            public_key=config.LANGFUSE_PUBLIC_GOAL_KEY,
            secret_key=config.LANGFUSE_SECRET_GOAL_KEY,
            host=config.LANGFUSE_HOST,
        )
        langfuse_goal_handler = CallbackHandler(public_key=config.LANGFUSE_PUBLIC_GOAL_KEY, update_trace=True)
        logger.info("[Langfuse][supervisor] Goal agent callback handler initialized")
    except Exception as e:
        logger.warning("[Langfuse][supervisor] Failed to create goal callback handler: %s: %s", type(e).__name__, e)

STREAM_WORD_GROUP_SIZE = 3
CONTEXT_KEY_MAX_PROMPT_TOKENS_LAST_RUN: str = "max_prompt_tokens_last_run"
CONTEXT_KEY_MAX_TOTAL_TOKENS_LAST_RUN: str = "max_total_tokens_last_run"


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

    def _extract_token_usage_from_event(
        self, data: dict[str, Any], max_prompt_tokens: int, max_total_tokens: int
    ) -> tuple[int, int]:
        """Extract token usage from chat model event data.

        Args:
            data: Event data dictionary containing output information
            max_prompt_tokens: Current maximum prompt tokens seen in this run
            max_total_tokens: Current maximum total tokens seen in this run

        Returns:
            Tuple of (updated_max_prompt_tokens, updated_max_total_tokens)

        """
        try:
            output = data.get("output") if isinstance(data, dict) else None
            usage = getattr(output, "usage_metadata", None) if output is not None else None
            response_meta = getattr(output, "response_metadata", None) if output is not None else None

            prompt_tokens = 0
            total_tokens = 0

            if isinstance(usage, dict):
                prompt_tokens = int(usage.get("input_tokens") or 0)
                total_tokens = int(usage.get("total_tokens") or 0)

            if isinstance(response_meta, dict):
                token_usage = response_meta.get("token_usage")
                if isinstance(token_usage, dict):
                    prompt_tokens = max(prompt_tokens, int(token_usage.get("prompt_tokens") or 0))
                    total_tokens = max(total_tokens, int(token_usage.get("total_tokens") or 0))

            updated_max_prompt_tokens = max(max_prompt_tokens, prompt_tokens)
            updated_max_total_tokens = max(max_total_tokens, total_tokens)

            return updated_max_prompt_tokens, updated_max_total_tokens
        except (TypeError, ValueError, AttributeError, KeyError) as exc:
            logger.debug("[SUPERVISOR] token_usage.extract.failed err=%s", exc)
            return max_prompt_tokens, max_total_tokens

    async def _load_user_context_from_external(self, user_id: UUID) -> UserContext:
        """Load UserContext from external FOS service with fallback."""
        try:
            repo = ExternalUserRepository()
            personal_info_service = PersonalInformationService()
            external_ctx = await repo.get_by_id(user_id)

            ctx = UserContext(user_id=user_id)
            personal_info = await personal_info_service.get_all_personal_info(str(user_id))
            if personal_info:
                ctx.personal_information = personal_info

            profile_details = await personal_info_service.get_profile_details(str(user_id))
            if profile_details:
                self._merge_profile_details(ctx, profile_details)
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
            repo = ExternalUserRepository()
            body = map_user_context_to_ai_context(user_context)
            logger.info(f"[SUPERVISOR] Prepared external payload: {json.dumps(body, ensure_ascii=False)}")

            metadata_payload = build_profile_metadata_payload(user_context)

            task_defs: list[tuple[str, Awaitable[dict[str, Any] | None]]] = [
                ("context_upsert", repo.upsert(user_context.user_id, body))
            ]
            if metadata_payload:
                logger.info(
                    "[SUPERVISOR] Prepared profile metadata payload for user %s: %s",
                    user_context.user_id,
                    json.dumps(metadata_payload, ensure_ascii=False),
                )
                task_defs.append(
                    (
                        "profile_metadata_update",
                        repo.update_user_profile_metadata(user_context.user_id, metadata_payload),
                    )
                )

            results = await asyncio.gather(*(coro for _, coro in task_defs), return_exceptions=True)

            context_upsert_success = False
            for (task_name, _), result in zip(task_defs, results, strict=True):
                if isinstance(result, Exception):
                    logger.warning(
                        "[SUPERVISOR] %s failed for user %s: %s",
                        task_name,
                        user_context.user_id,
                        result,
                    )
                    continue

                if task_name == "context_upsert":
                    if result is not None:
                        logger.info(
                            "[SUPERVISOR] External API acknowledged update for user %s",
                            user_context.user_id,
                        )
                        context_upsert_success = True
                    else:
                        logger.warning(
                            "[SUPERVISOR] External API returned no body or 404 for user %s",
                            user_context.user_id,
                        )
                elif task_name == "profile_metadata_update":
                    if result is not None:
                        logger.info(
                            "[SUPERVISOR] Profile metadata updated for user %s",
                            user_context.user_id,
                        )
                    else:
                        logger.warning(
                            "[SUPERVISOR] Profile metadata update returned no body for user %s",
                            user_context.user_id,
                        )

            return context_upsert_success
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
        if isinstance(data, Command):
            return sources

        if current_agent in ["transfer_to_finance_agent", "transfer_to_goal_agent"]:
            return sources

        if name == "search_kb":
            return sources

        if not isinstance(data, dict) or "output" not in data:
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

            metadata = item.get("metadata", {})
            if isinstance(metadata, dict) and metadata.get("content_source") == "internal":
                logger.info(f"[SUPERVISOR] Skipping internal source: {source_content}")
                continue

            new_source = {"name": get_source_name(name), "url": source_content}

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

    def _merge_profile_details(self, ctx: UserContext, details: dict[str, Any]) -> None:
        """Merge birth date and location fields from user profile service."""
        birth_date = details.get("birth_date")
        if isinstance(birth_date, str) and birth_date.strip():
            ctx.identity.birth_date = birth_date.strip()

        location = details.get("location")
        if isinstance(location, str) and location.strip():
            parts = [p.strip() for p in location.split(",") if p.strip()]
            city: str | None = None
            region: str | None = None
            if len(parts) >= 2:
                city, region = parts[0], parts[1]
            elif parts:
                city, region = location_normalizer.normalize(parts[0])
            else:
                city, region = None, None

            if city:
                ctx.location.city = city
            if region:
                ctx.location.region = region

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

        from app.services.llm.prompt_loader import prompt_loader

        system_prompt = prompt_loader.load("conversation_summarizer_system_prompt")

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

    async def initialize(self, *, user_id: UUID, voice: bool = False) -> dict[str, Any]:
        """Initialize the supervisor service."""
        thread_id = str(uuid4())
        queue = get_sse_queue(thread_id)

        await queue.put({"event": "conversation.started", "data": {"thread_id": thread_id}})

        session_store = get_session_store()
        uid: UUID = user_id
        ctx = await self._load_user_context_from_external(uid)

        has_plaid_accounts = False
        has_financial_data = False
        try:
            db_service = get_database_service()
            async with db_service.get_session() as session:
                repo = db_service.get_finance_repository(session)
                has_plaid_accounts = await repo.user_has_any_accounts(uid)
                if has_plaid_accounts:
                    has_financial_data = True
                else:
                    has_financial_data = await repo.user_has_manual_financial_data(uid)
        except Exception as e:
            logger.warning(f"[SUPERVISOR] Failed to check financial accounts for user {uid}: {e}")
            has_financial_data = has_plaid_accounts

        logger.info(
            f"[SUPERVISOR] User {uid} financial flags -> plaid_accounts={has_plaid_accounts}, "
            f"financial_data={has_financial_data}"
        )
        await session_store.set_session(
            thread_id,
            {
                "user_id": str(uid),
                "user_context": ctx.model_dump(mode="json"),
                "conversation_messages": [],
                "has_financial_accounts": has_plaid_accounts,
                "has_plaid_accounts": has_plaid_accounts,
                "has_financial_data": has_financial_data,
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

        welcome_cleaned = _strip_emojis(welcome)
        await queue.put({"event": "message.completed", "data": {"text": welcome_cleaned}})

        if voice:
            try:
                # Start audio service for this thread if not already started
                await start_audio_service_for_thread(thread_id)
                logger.info(f"[SUPERVISOR] Started audio service for thread_id: {thread_id}")
                audio_service = get_audio_service()
                await audio_service._synthesize_and_stream_audio(
                    thread_id,
                    welcome_cleaned,
                    config.TTS_VOICE_ID,
                    config.TTS_OUTPUT_FORMAT,
                    get_audio_queue(thread_id),
                )
                logger.info(f"[SUPERVISOR] Welcome audio generated for thread_id: {thread_id}")
            except Exception as e:
                logger.error(f"[SUPERVISOR] Failed to generate welcome audio for thread_id {thread_id}: {e}")

        if has_financial_data:
            try:
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

    async def process_message(self, *, thread_id: str, text: str, voice: bool = True) -> None:
        if not text or not text.strip():
            raise ValueError("Message text must not be empty")

        q = get_sse_queue(thread_id)
        current_description = _get_random_step_planning_current()
        await q.put(
            {
                "event": "step.update",
                "data": {
                    "status": "processing",
                    "description": current_description,
                },
            }
        )

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

        # Add goal agent callback to configurable for propagation to workers
        if langfuse_goal_handler:
            configurable["langfuse_callback_goals"] = langfuse_goal_handler

        emitted_handoff_back_keys: set[str] = set()
        current_agent_tool: Optional[str] = None
        active_handoffs: set[str] = set()
        handoff_timeline_ids: dict[str, str] = {}

        latest_response_text: Optional[str] = None
        supervisor_latest_response_text: Optional[str] = None
        response_event_count = 0
        hit_guardrail: bool = False
        max_prompt_tokens_this_run: int = 0
        max_total_tokens_this_run: int = 0

        navigation_events_to_emit: list[dict[str, Any]] = []
        seen_navigation_events: set[str] = set()

        metadata: dict[str, str] = {"langfuse_session_id": thread_id}
        if user_id:
            metadata["langfuse_user_id"] = str(user_id)

        callbacks_list = []
        if langfuse_handler:
            callbacks_list.append(langfuse_handler)

        config_payload: dict[str, Any] = {
            "callbacks": callbacks_list,
            "configurable": configurable,
            "thread_id": thread_id,
        }
        if metadata:
            config_payload["metadata"] = metadata

        async for event in graph.astream_events(
            {
                "messages": [{"role": "user", "content": text}],
                "sources": sources,
                "context": {
                    "thread_id": thread_id,
                    CONTEXT_KEY_MAX_PROMPT_TOKENS_LAST_RUN: session_ctx.get(CONTEXT_KEY_MAX_PROMPT_TOKENS_LAST_RUN),
                    CONTEXT_KEY_MAX_TOTAL_TOKENS_LAST_RUN: session_ctx.get(CONTEXT_KEY_MAX_TOTAL_TOKENS_LAST_RUN),
                },
                "navigation_events": None,
            },
            version="v2",
            config=config_payload,
            stream_mode="values",
            subgraphs=True,
        ):
            name = event.get("name")
            etype = event.get("event")
            raw_data = event.get("data")
            data = {} if isinstance(raw_data, Command) else raw_data if isinstance(raw_data, dict) else {}

            if etype == "on_chat_model_end" and name == "SafeChatCerebras":
                prev_max_prompt_tokens_this_run = max_prompt_tokens_this_run
                prev_max_total_tokens_this_run = max_total_tokens_this_run

                max_prompt_tokens_this_run, max_total_tokens_this_run = self._extract_token_usage_from_event(
                    data, max_prompt_tokens_this_run, max_total_tokens_this_run
                )

                if (
                    max_prompt_tokens_this_run != prev_max_prompt_tokens_this_run
                    or max_total_tokens_this_run != prev_max_total_tokens_this_run
                ):
                    logger.debug(
                        "[SUPERVISOR] token_usage.update thread_id=%s "
                        "max_prompt_tokens_this_run=%s max_total_tokens_this_run=%s",
                        thread_id,
                        max_prompt_tokens_this_run,
                        max_total_tokens_this_run,
                    )

            response_text = ""
            response_author: str | None = None
            try:
                if isinstance(data, dict) and data:
                    output_payload = data.get("output")
                    if isinstance(output_payload, dict):
                        messages_payload = output_payload.get("messages")
                        if isinstance(messages_payload, list):
                            for msg in reversed(messages_payload):
                                raw_content: Any = None
                                if isinstance(msg, dict):
                                    raw_content = msg.get("content")
                                else:
                                    raw_content = getattr(msg, "content", None)

                                candidate = self._content_to_text(raw_content)
                                if candidate and candidate.strip():
                                    msg_name = msg.get("name") if isinstance(msg, dict) else getattr(msg, "name", None)

                                    msg_meta = {}
                                    try:
                                        if isinstance(msg, dict):
                                            msg_meta = msg.get("response_metadata", {}) or {}
                                        else:
                                            msg_meta = getattr(msg, "response_metadata", {}) or {}
                                    except Exception:
                                        msg_meta = {}

                                    if msg_meta.get("is_handoff_back"):
                                        continue

                                    if msg_name and msg_name != "supervisor":
                                        continue

                                    response_text = candidate.strip()
                                    response_author = msg_name
                                    break

                if response_text:
                    prev_latest = (latest_response_text[:80] + "...") if latest_response_text else None
                    latest_response_text = response_text
                    if name == "supervisor":
                        if response_author not in (None, "supervisor"):
                            logger.info(
                                "[TRACE] supervisor.buffer.skip reason=non_supervisor_message author=%s",
                                response_author,
                            )
                            continue
                        prev_super = (
                            (supervisor_latest_response_text[:80] + "...") if supervisor_latest_response_text else None
                        )
                        supervisor_latest_response_text = response_text
                        logger.info(
                            f"[TRACE] supervisor.buffer.update from={prev_super} to={(supervisor_latest_response_text[:80] + '...') if supervisor_latest_response_text else None}"
                        )
                    response_event_count += 1
                    logger.info(
                        f"[TRACE] latest.update event={name} type={etype} count={response_event_count} "
                        f"from={prev_latest} to={(latest_response_text[:80] + '...') if latest_response_text else None}"
                    )

            except Exception as e:
                logger.exception("Error processing supervisor event: %s", e)

            if etype == "on_chat_model_stream" and name == "SafeChatCerebras" and not active_handoffs:
                try:
                    chunk = data.get("chunk") if isinstance(data, dict) else None
                    chunk_text = self._content_to_text(getattr(chunk, "content", "")) if chunk else ""
                    if chunk_text:
                        hit_guardrail = hit_guardrail or self._has_guardrail_intervention(chunk_text)
                        cleaned_chunk = _strip_emojis(self._strip_guardrail_marker(chunk_text))
                        if cleaned_chunk.strip():
                            await q.put({"event": "token.delta", "data": {"text": cleaned_chunk, "sources": sources}})
                except Exception as stream_exc:
                    logger.debug(f"[TRACE] supervisor.stream.chunk.error err={stream_exc}")

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
                    elif tool_name == "transfer_to_finance_capture_agent":
                        description = _get_random_finance_capture_current()

                    task_text = ""
                    try:
                        input_payload = data.get("input") if isinstance(data, dict) else None
                        if isinstance(input_payload, dict):
                            task_text = (
                                input_payload.get("task_description")
                                or input_payload.get("task")
                                or input_payload.get("content")
                                or ""
                            )
                        elif isinstance(input_payload, str):
                            task_text = input_payload
                    except Exception:
                        task_text = ""

                    timeline_item_id = str(uuid4())
                    handoff_timeline_ids[tool_name] = timeline_item_id
                    await q.put(
                        {
                            "event": "source.search.start",
                            "data": {
                                "tool": tool_name,
                                "source": tool_name.replace("transfer_to_", "").replace("_", " ").title(),
                                "description": description,
                                "timeline_item_id": timeline_item_id,
                            },
                        }
                    )
                    schedule_extended_description_update(
                        queue=q,
                        tool=tool_name,
                        source=tool_name.replace("transfer_to_", "").replace("_", " ").title(),
                        description=task_text or description,
                        timeline_item_id=timeline_item_id,
                        phase="start",
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
                    output = data.get("output", {}) if isinstance(data, dict) else {}
                    if isinstance(output, dict):
                        if "sources" in output and output["sources"]:
                            handoff_sources = output["sources"]
                            if handoff_sources:
                                sources.extend(handoff_sources)
                                logger.info(f"[TRACE] supervisor.handoff.sources_added count={len(handoff_sources)}")

                        nav_events = output.get("navigation_events")
                        if isinstance(nav_events, list):
                            for nav_event in nav_events:
                                event_name = nav_event.get("event")
                                event_data = nav_event.get("data", {})
                                event_key = f"{event_name}:{json.dumps(event_data, sort_keys=True)}"
                                if event_key not in seen_navigation_events:
                                    seen_navigation_events.add(event_key)
                                    navigation_events_to_emit.append(nav_event)
                                    logger.info(f"[SUPERVISOR] Collected navigation event: {event_name}")

                        messages = output.get("messages")
                        if isinstance(messages, list) and messages:

                            def _meta(msg):
                                try:
                                    if isinstance(msg, dict):
                                        return msg.get("response_metadata", {}) or {}
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
                                if (
                                    dedupe_key not in emitted_handoff_back_keys
                                    and current_agent_tool
                                    and current_agent_tool in active_handoffs
                                ):
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
                                    elif current_agent_tool == "transfer_to_finance_capture_agent":
                                        description = _get_random_finance_capture_completed()

                                    supervisor_name = "Supervisor"
                                    timeline_item_id = handoff_timeline_ids.get(current_agent_tool or "")
                                    agent_result_text = extract_agent_result_text(messages)
                                    await q.put(
                                        {
                                            "event": "source.search.end",
                                            "data": {
                                                "tool": back_tool,
                                                "source": supervisor_name,
                                                "description": description,
                                                "timeline_item_id": timeline_item_id,
                                            },
                                        }
                                    )
                                    schedule_extended_description_update(
                                        queue=q,
                                        tool=back_tool,
                                        source=supervisor_name,
                                        description=description,
                                        timeline_item_id=timeline_item_id,
                                        phase="end",
                                        result_text=agent_result_text or supervisor_latest_response_text,
                                    )
                                    handoff_timeline_ids.pop(current_agent_tool or "", None)
                                    current_agent_tool = None
                except Exception as e:
                    logger.info(f"[TRACE] chain_end.handoff_close.error err={e}")

                # If supervisor produced text but a handoff remains open (missing back signal), close it conservatively
                if name == "supervisor" and supervisor_latest_response_text and active_handoffs:
                    try:
                        for tool_name in list(active_handoffs):
                            description = "Returned from source"
                            if tool_name == "transfer_to_finance_agent":
                                description = _get_random_finance_completed()
                            elif tool_name == "transfer_to_goal_agent":
                                description = _get_random_budget_completed()
                            elif tool_name == "transfer_to_wealth_agent":
                                description = _get_random_wealth_completed()
                            elif tool_name == "transfer_to_finance_capture_agent":
                                description = _get_random_finance_capture_completed()

                            timeline_item_id = handoff_timeline_ids.get(tool_name)
                            await q.put(
                                {
                                    "event": "source.search.end",
                                    "data": {
                                        "tool": "transfer_back_to_supervisor",
                                        "source": "Supervisor",
                                        "description": description,
                                        "timeline_item_id": timeline_item_id,
                                    },
                                }
                            )
                            schedule_extended_description_update(
                                queue=q,
                                tool="transfer_back_to_supervisor",
                                source="Supervisor",
                                description=description,
                                timeline_item_id=timeline_item_id,
                                phase="end",
                                result_text=supervisor_latest_response_text,
                            )
                            active_handoffs.discard(tool_name)
                            handoff_timeline_ids.pop(tool_name, None)
                        current_agent_tool = None
                        logger.info("[TRACE] supervisor.handoff.conservative_close active_handoffs_cleared")
                    except Exception as e:
                        logger.info(f"[TRACE] handoff.conservative_close.error err={e}")

        try:
            final_text = supervisor_latest_response_text
            if final_text:
                final_text_to_emit = _strip_emojis(
                    self._strip_guardrail_marker(final_text) if hit_guardrail else final_text
                )

                for nav_event in navigation_events_to_emit:
                    await q.put(
                        {
                            "event": nav_event.get("event"),
                            "data": nav_event.get("data", {}),
                        }
                    )
                    logger.info(f"[SUPERVISOR] Emitted navigation event: {nav_event.get('event')}")

                await q.put({"event": "message.completed", "data": {"content": final_text_to_emit}})

                # Generate audio only if voice=True
                if voice:
                    try:
                        audio_service = get_audio_service()
                        await audio_service._synthesize_and_stream_audio(
                            thread_id,
                            final_text_to_emit,
                            config.TTS_VOICE_ID,
                            config.TTS_OUTPUT_FORMAT,
                            get_audio_queue(thread_id),
                        )
                        logger.info(f"[SUPERVISOR] Triggered audio synthesis for thread_id: {thread_id}")
                    except Exception as e:
                        logger.error(f"[SUPERVISOR] Failed to trigger audio synthesis for thread_id {thread_id}: {e}")
                else:
                    logger.info(f"[SUPERVISOR] Audio generation disabled for thread_id: {thread_id}")
        except Exception as e:
            logger.error(f"[DEBUG] Error sending message.completed: {e}")

        completed_description = _get_random_step_planning_completed()
        await q.put(
            {
                "event": "step.update",
                "data": {
                    "status": "presented",
                    "description": completed_description,
                },
            }
        )

        try:
            final_text = supervisor_latest_response_text
            if final_text:
                assistant_response = _strip_emojis(
                    self._strip_guardrail_marker(final_text) if hit_guardrail else final_text
                ).strip()
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

            session_ctx[CONTEXT_KEY_MAX_PROMPT_TOKENS_LAST_RUN] = int(max_prompt_tokens_this_run)
            session_ctx[CONTEXT_KEY_MAX_TOTAL_TOKENS_LAST_RUN] = int(max_total_tokens_this_run)
            session_ctx["conversation_messages"] = conversation_messages
            await session_store.set_session(thread_id, session_ctx)
            logger.info(f"Stored conversation for thread {thread_id}: {len(conversation_messages)} messages")

            user_id = session_ctx.get("user_id")
            if user_id:
                user_ctx_dict = session_ctx.get("user_context", {})
                if user_ctx_dict:
                    ctx = UserContext.model_validate(user_ctx_dict)
                    ctx = await self._load_user_context_from_external(ctx.user_id)
                    await self._export_user_context_to_external(ctx)

        except Exception as e:
            logger.exception(f"Failed to store conversation for thread {thread_id}: {e}")

    async def resume_interrupt(
        self, *, thread_id: str, decision: dict[str, Any] | str | bool, confirm_id: Optional[str] = None
    ) -> None:
        """Resume a paused graph run for this thread with a decision payload.

        The decision value becomes the return value of interrupt() inside the node.
        """
        q = get_sse_queue(thread_id)
        await q.put(
            {
                "event": "step.update",
                "data": {
                    "status": "processing",
                    "description": "Resuming approval",
                },
            }
        )
        await q.put({"event": "confirm.response", "data": {"decision": decision}})

        graph: CompiledStateGraph = get_supervisor_graph()
        session_store: InMemorySessionStore = get_session_store()
        session_ctx = await session_store.get_session(thread_id) or {}

        user_id = session_ctx.get("user_id")
        configurable = {
            "thread_id": thread_id,
            "session_id": thread_id,
            **session_ctx,
            "user_id": user_id,
            "confirm_decision": decision,
            "confirm_id": confirm_id,
        }

        config_payload: dict[str, Any] = {
            "configurable": configurable,
            "thread_id": thread_id,
        }

        # Resume execution; the result is the updated supervisor state
        result = await graph.ainvoke(Command(resume=decision), config=config_payload)

        # Emit a final message if present
        try:
            response_text = ""
            completion_context: dict[str, Any] | None = None
            if isinstance(result, dict):
                completion_context = result.get("completion_context")
                if isinstance(result.get("messages"), list):
                    for msg in reversed(result["messages"]):
                        content = getattr(msg, "content", None)
                        if isinstance(content, str) and content.strip():
                            response_text = content.strip()
                            break

            if response_text:
                streaming_text = ""
                try:
                    loop = asyncio.get_running_loop()
                    streaming_text = await loop.run_in_executor(
                        None,
                        generate_completion_response,
                        response_text,
                        completion_context,
                    )
                except Exception as exc:
                    logger.warning("[TRACE] resume_interrupt.completion_stream.error err=%s", exc)
                if not streaming_text:
                    streaming_text = response_text

                cleaned_stream_text = _strip_emojis(self._strip_guardrail_marker(streaming_text or ""))
                words = cleaned_stream_text.split(" ")
                sources: list[dict[str, Any]] = []
                for i in range(0, len(words), STREAM_WORD_GROUP_SIZE):
                    word_group = " ".join(words[i : i + STREAM_WORD_GROUP_SIZE]).strip()
                    if not word_group:
                        continue
                    await q.put({"event": "token.delta", "data": {"text": f"{word_group} ", "sources": sources}})
                    await asyncio.sleep(0)

                final_completion_text = cleaned_stream_text.strip() or response_text
                await q.put({"event": "message.completed", "data": {"content": final_completion_text}})
        except Exception:
            pass

        await q.put(
            {
                "event": "step.update",
                "data": {"status": "presented", "description": _get_random_step_planning_completed()},
            }
        )


supervisor_service = SupervisorService()
