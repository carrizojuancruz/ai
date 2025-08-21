from __future__ import annotations

import json
import logging
import os
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from langfuse.callback import CallbackHandler

from app.agents.onboarding.state import OnboardingState
from app.core.app_state import (
    get_last_emitted_text,
    get_onboarding_agent,
    get_sse_queue,
    get_thread_state,
    register_thread,
    set_last_emitted_text,
    set_thread_state,
)
from app.repositories.session_store import get_session_store

logger = logging.getLogger(__name__)

langfuse_handler = CallbackHandler(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST"),
)


class OnboardingService:
    async def _export_user_context(self, state: OnboardingState, thread_id: str) -> None:
        try:
            session_store = get_session_store()
            session_ctx = await session_store.get_session(thread_id) or {}
            if session_ctx.get("fos_exported"):
                return

            from app.services.external_context.client import ExternalUserRepository
            from app.services.external_context.mapping import map_user_context_to_ai_context

            repo = ExternalUserRepository()
            body = map_user_context_to_ai_context(state.user_context)
            logger.info("[USER CONTEXT EXPORT] Prepared external payload: %s", json.dumps(body, ensure_ascii=False))
            resp = await repo.upsert(state.user_id, body)
            if resp is not None:
                logger.info("[USER CONTEXT EXPORT] External API acknowledged update for user %s", state.user_id)
            else:
                logger.warning("[USER CONTEXT EXPORT] External API returned no body or 404 for user %s", state.user_id)

            session_ctx["fos_exported"] = True
            await session_store.set_session(thread_id, session_ctx)
        except Exception as e:
            logger.error("[USER CONTEXT EXPORT] Failed to export user context: %s", e)

    async def initialize(self, *, user_id: str | None = None) -> dict[str, Any]:
        thread_id = str(uuid4())

        if user_id and user_id.strip():
            try:
                user_uuid = UUID(user_id)
            except ValueError:
                logger.warning(f"Invalid UUID provided: {user_id}, generating new one")
                user_uuid = uuid4()
        else:
            user_uuid = uuid4()

        state = OnboardingState(user_id=user_uuid)

        try:
            from app.services.external_context.client import ExternalUserRepository
            from app.services.external_context.mapping import map_ai_context_to_user_context

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
        async for event, state in agent.process_message_with_events(user_uuid, "", state):
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
                await self._export_user_context(state, thread_id)
            await queue.put(event)
            final_state = state

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

        user_text = ""
        if type == "text" and text is not None:
            user_text = text
        elif type == "choice" and choice_ids:
            if state.current_interaction_type == "binary_choice":
                if state.current_binary_choices:
                    for choice_id in choice_ids:
                        if choice_id == state.current_binary_choices.get("primary_choice", {}).get("id"):
                            user_text = state.current_binary_choices["primary_choice"]["value"]
                        elif choice_id == state.current_binary_choices.get("secondary_choice", {}).get("id"):
                            user_text = state.current_binary_choices["secondary_choice"]["value"]
            else:
                choice_values = []
                for choice_id in choice_ids:
                    for choice in state.current_choices:
                        if choice.get("id") == choice_id:
                            choice_values.append(choice.get("value", choice_id))
                            break
                user_text = ", ".join(choice_values) if choice_values else ", ".join(choice_ids)
        elif type == "control" and action in {"back", "skip"}:
            set_thread_state(thread_id, state)
            await get_sse_queue(thread_id).put(
                {
                    "event": "step.update",
                    "data": {"status": "completed", "step_id": state.current_step.value},
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
        await self._export_user_context(state, thread_id)


onboarding_service = OnboardingService()
