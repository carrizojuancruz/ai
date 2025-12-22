from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException

from app.agents.onboarding.state import OnboardingState
from app.agents.onboarding.types import InteractionType  # noqa: F401
from app.core.app_state import (
    get_last_emitted_text,
    get_onboarding_agent,
    get_sse_queue,
    get_thread_lock,
    get_thread_state,
    register_thread,
    set_last_emitted_text,
    set_thread_state,
)
from app.repositories.session_store import get_session_store
from app.services.external_context.user.mapping import (
    map_ai_context_to_user_context,
    map_user_context_to_ai_context,
)
from app.services.external_context.user.profile_metadata import build_profile_metadata_payload
from app.services.external_context.user.repository import ExternalUserRepository
from app.services.user_context_cache import get_user_context_cache

logger = logging.getLogger(__name__)


class OnboardingService:
    async def _export_user_context(self, state: OnboardingState, thread_id: str) -> None:
        try:
            session_store = get_session_store()
            session_ctx = await session_store.get_session(thread_id) or {}
            if session_ctx.get("fos_exported"):
                return

            repo = ExternalUserRepository()
            body = map_user_context_to_ai_context(state.user_context)
            logger.info("[USER CONTEXT EXPORT] Prepared external payload: %s", json.dumps(body, ensure_ascii=False))

            metadata_payload = build_profile_metadata_payload(state.user_context)

            task_defs: list[tuple[str, Awaitable[dict[str, Any] | None]]] = [
                ("context_upsert", repo.upsert(state.user_id, body))
            ]
            if metadata_payload:
                logger.info(
                    "[USER CONTEXT EXPORT] Prepared profile metadata payload for user %s: %s",
                    state.user_id,
                    json.dumps(metadata_payload, ensure_ascii=False),
                )
                task_defs.append(
                    (
                        "profile_metadata_update",
                        repo.update_user_profile_metadata(state.user_id, metadata_payload),
                    )
                )

            results = await asyncio.gather(*(coro for _, coro in task_defs), return_exceptions=True)

            for (task_name, _), result in zip(task_defs, results, strict=True):
                if isinstance(result, Exception):
                    logger.warning(
                        "[USER CONTEXT EXPORT] %s failed for user %s: %s",
                        task_name,
                        state.user_id,
                        result,
                    )
                    continue

                if task_name == "context_upsert":
                    if result is not None:
                        logger.info(
                            "[USER CONTEXT EXPORT] External API acknowledged update for user %s",
                            state.user_id,
                        )
                    else:
                        logger.warning(
                            "[USER CONTEXT EXPORT] External API returned no body or 404 for user %s",
                            state.user_id,
                        )
                elif task_name == "profile_metadata_update":
                    if result is not None:
                        logger.info(
                            "[USER CONTEXT EXPORT] Profile metadata updated for user %s",
                            state.user_id,
                        )
                    else:
                        logger.warning(
                            "[USER CONTEXT EXPORT] Profile metadata update returned no body for user %s",
                            state.user_id,
                        )

            try:
                cache = get_user_context_cache()
                cache.invalidate(state.user_id)
                logger.info("[USER CONTEXT EXPORT] Invalidated user context cache for user %s", state.user_id)
            except Exception as cache_err:
                logger.warning(
                    "[USER CONTEXT EXPORT] Failed to invalidate cache for user %s: %s", state.user_id, cache_err
                )

            session_ctx["fos_exported"] = True
            await session_store.set_session(thread_id, session_ctx)
        except Exception as e:
            logger.error("[USER CONTEXT EXPORT] Failed to export user context: %s", e)

    async def initialize(
        self, *, user_id: str | None = None, show_complete_welcome_message: bool = True
    ) -> dict[str, Any]:
        thread_id = str(uuid4())

        if user_id and user_id.strip():
            try:
                user_uuid = UUID(user_id)
            except ValueError:
                logger.warning(f"Invalid UUID provided: {user_id}, generating new one")
                user_uuid = uuid4()
        else:
            user_uuid = uuid4()

        state = OnboardingState(user_id=user_uuid, show_complete_welcome_message=show_complete_welcome_message)

        try:
            repo = ExternalUserRepository()
            external_ctx = await repo.get_by_id(user_uuid)
            if external_ctx:
                logger.info(f"[USER CONTEXT UPDATE] External AI Context found for user: {user_uuid}")
                map_ai_context_to_user_context(external_ctx, state.user_context)
                state.user_context.sync_flat_to_nested()
        except Exception as e:
            logger.warning(f"Context prefill skipped due to error: {e}")

        logger.info(f"[USER CONTEXT UPDATE] Starting onboarding for user: {user_uuid}")
        logger.info(
            f"[USER CONTEXT UPDATE] Initial context: {json.dumps(state.user_context.model_dump(mode='json'), indent=2)}"
        )

        register_thread(thread_id, state)
        queue = get_sse_queue(thread_id)

        session_store = get_session_store()
        await session_store.set_session(
            thread_id,
            {
                "user_id": str(user_uuid),
            },
        )

        await queue.put({"event": "conversation.started", "data": {"thread_id": thread_id}})

        agent = get_onboarding_agent()

        final_state = None
        stream_acc = ""
        async for event, current_state in agent.process_message_with_events(user_uuid, "", state):
            if not event:
                continue
            ev_name = event.get("event")
            if ev_name == "token.delta":
                raw = event.get("data", {}).get("text", "")
                if raw:
                    if raw.startswith(stream_acc):
                        delta = raw[len(stream_acc) :]
                        stream_acc = raw
                    else:
                        delta = raw
                        stream_acc = stream_acc + delta
                    if delta:
                        set_last_emitted_text(thread_id, delta)
                        await queue.put({"event": "token.delta", "data": {"text": delta}})
                continue
            if ev_name == "onboarding.status" and (event.get("data", {}) or {}).get("status") == "done":
                await self._export_user_context(current_state, thread_id)
            await queue.put(event)
            final_state = current_state

        set_thread_state(thread_id, final_state)

        return {
            "thread_id": thread_id,
            "welcome": final_state.last_agent_response or "",
            "sse_url": f"/onboarding/sse/{thread_id}",
        }

    async def process_message(
        self,
        *,
        thread_id: str,
        type: str,
        text: str | None = None,
        choice_ids: list[str] | None = None,
        action: str | None = None,
    ) -> dict[str, Any]:
        state = get_thread_state(thread_id)
        if state is None:
            raise HTTPException(status_code=404, detail="Thread not found")

        if isinstance(state, dict):
            from app.agents.onboarding.state import OnboardingState

            state = OnboardingState(**state)

        lock = get_thread_lock(thread_id)
        async with lock:
            user_text = ""
            if type == "text" and text is not None:
                user_text = text
            elif type == "choice" and choice_ids:
                choice_values = []
                for choice_id in choice_ids:
                    for choice in state.current_choices:
                        if choice.id == choice_id:
                            choice_values.append(choice.value or choice_id)
                            break
                user_text = ", ".join(choice_values) if choice_values else ", ".join(choice_ids)
            elif type == "control" and action in {"back", "skip"}:
                set_thread_state(thread_id, state)
                await get_sse_queue(thread_id).put(
                    {
                        "event": "step.update",
                        "data": {"status": "completed", "step_id": state.current_flow_step.value},
                    }
                )
                return {"status": "accepted"}

            agent = get_onboarding_agent()
            q = get_sse_queue(thread_id)

            prev_text = get_last_emitted_text(thread_id)

            state.last_user_message = user_text

            final_state = None
            stream_acc = ""
            async for event, current_state in agent.process_message_with_events(state.user_id, user_text, state):
                if not event:
                    continue
                ev_name = event.get("event")
                if ev_name == "token.delta":
                    raw = event.get("data", {}).get("text", "")
                    if raw:
                        if raw.startswith(stream_acc):
                            delta = raw[len(stream_acc) :]
                            stream_acc = raw
                        else:
                            delta = raw
                            stream_acc = stream_acc + delta
                        if delta:
                            set_last_emitted_text(thread_id, delta)
                            await q.put({"event": "token.delta", "data": {"text": delta}})
                    continue
                if ev_name == "onboarding.status" and (event.get("data", {}) or {}).get("status") == "done":
                    await self._export_user_context(current_state, thread_id)
                await q.put(event)
                final_state = current_state

            if not (final_state.last_agent_response or ""):
                text_out, ensured_state = await agent.process_message(state.user_id, user_text, final_state)
                final_state = ensured_state
                if text_out and text_out != prev_text:
                    await q.put({"event": "message.completed", "data": {"text": text_out}})
                    set_last_emitted_text(thread_id, text_out)

            set_thread_state(thread_id, final_state)

            return {"status": "accepted"}

    async def finalize(self, *, thread_id: str) -> None:
        state = get_thread_state(thread_id)
        if state is None:
            raise HTTPException(status_code=404, detail="Thread not found")

        if isinstance(state, dict):
            from app.agents.onboarding.state import OnboardingState

            state = OnboardingState(**state)

        state.ready_for_completion = True
        state.user_context.ready_for_orchestrator = True
        set_thread_state(thread_id, state)
        await self._export_user_context(state, thread_id)

        from app.core.app_state import drop_sse_queue

        drop_sse_queue(thread_id)


onboarding_service = OnboardingService()
