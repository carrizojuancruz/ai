from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

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

langfuse_handler = CallbackHandler(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST"),
)


class OnboardingService:
    async def initialize(self) -> dict[str, Any]:
        thread_id = str(uuid4())
        user_id = uuid4()
        state = OnboardingState(user_id=user_id)

        register_thread(thread_id, state)
        queue = get_sse_queue(thread_id)

        await queue.put({"event": "conversation.started", "data": {"thread_id": thread_id}})

        agent = get_onboarding_agent()

        final_state = None
        async for event, state in agent.process_message_with_events(user_id, "", state):
            if event:
                if event.get("event") == "token.delta":
                    set_last_emitted_text(thread_id, event.get("data", {}).get("text", ""))
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
            user_text = ", ".join(choice_ids)
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

        final_state = None
        async for event, current_state in agent.process_message_with_events(state.user_id, user_text, state):
            if event:
                if event.get("event") == "token.delta":
                    set_last_emitted_text(thread_id, event.get("data", {}).get("text", ""))
                await q.put(event)
            final_state = current_state

        if not (final_state.last_agent_response or ""):
            text_out, ensured_state = await agent.process_message(state.user_id, user_text, final_state)
            final_state = ensured_state
            if text_out and text_out != prev_text:
                await q.put({"event": "token.delta", "data": {"text": text_out}})
                set_last_emitted_text(thread_id, text_out)

        set_thread_state(thread_id, final_state)

        current_text = get_last_emitted_text(thread_id)
        if current_text == prev_text:
            final_text = final_state.last_agent_response or ""
            if final_text and final_text != prev_text:
                await q.put({"event": "token.delta", "data": {"text": final_text}})
                set_last_emitted_text(thread_id, final_text)

        return {"status": "accepted"}


onboarding_service = OnboardingService()
