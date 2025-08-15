from __future__ import annotations

import asyncio
import json
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents.onboarding import OnboardingState
from app.core.app_state import get_supervisor_graph
from app.core.app_state import (
    get_last_emitted_text,
    get_onboarding_agent,
    get_sse_queue,
    get_thread_state,
    get_user_sessions,
    register_thread,
    set_last_emitted_text,
    set_thread_state,
)

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])




@router.get("/status/{user_id}")
async def get_onboarding_status(user_id) -> dict:
    sessions = get_user_sessions()
    state = sessions.get(user_id)
    if state is None:
        return {"error": "User session not found"}
    return {
        "user_id": str(user_id),
        "current_step": state.current_step.value,
        "completed_steps": [step.value for step in state.completed_steps],
        "skipped_steps": [step.value for step in state.skipped_steps],
        "ready_for_orchestrator": state.user_context.ready_for_orchestrator,
        "user_context": state.user_context.model_dump(),
        "semantic_memories_count": len(state.semantic_memories),
        "blocked_topics_count": len(state.blocked_topics),
        "conversation_turns": state.turn_number,
    }


class InitializeResponse(BaseModel):
    thread_id: str
    welcome: str
    sse_url: str


@router.post("/initialize", response_model=InitializeResponse)
async def initialize_onboarding() -> InitializeResponse:
    thread_id = str(uuid4())
    user_id = uuid4()
    state = OnboardingState(user_id=user_id)

    register_thread(thread_id, state)
    queue = get_sse_queue(thread_id)

    await queue.put({"event": "conversation.started", "data": {"thread_id": thread_id}})

    agent = get_onboarding_agent()

    prev_text = get_last_emitted_text(thread_id)

    async def emit(evt: dict) -> None:
        if isinstance(evt, dict) and evt.get("event") == "token.delta":
            set_last_emitted_text(thread_id, evt.get("data", {}).get("text", ""))
        await queue.put(evt)

    final_state = await agent.process_message_with_events(user_id, "", state, emit)

    if not (final_state.last_agent_response or ""):
        text, ensured_state = await agent.process_message(user_id, "", final_state)
        final_state = ensured_state
        if text and text != prev_text:
            await queue.put({"event": "token.delta", "data": {"text": text}})
            set_last_emitted_text(thread_id, text)

    set_thread_state(thread_id, final_state)

    current_text = get_last_emitted_text(thread_id)
    if current_text == prev_text:
        final_text = final_state.last_agent_response or ""
        if final_text and final_text != prev_text:
            await queue.put({"event": "token.delta", "data": {"text": final_text}})
            set_last_emitted_text(thread_id, final_text)

    return InitializeResponse(
        thread_id=thread_id,
        welcome=final_state.last_agent_response or "",
        sse_url=f"/onboarding/sse/{thread_id}",
    )


class MessagePayload(BaseModel):
    thread_id: str
    type: str  # "text" | "choice" | "control"
    text: str | None = None
    step_id: str | None = None
    choice_ids: list[str] | None = None
    action: str | None = None  # "back" | "skip"


@router.post("/message")
async def onboarding_message(payload: MessagePayload) -> dict:
    state = get_thread_state(payload.thread_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    user_text = ""
    if payload.type == "text" and payload.text is not None:
        user_text = payload.text
    elif payload.type == "choice" and payload.choice_ids:
        user_text = ", ".join(payload.choice_ids)
    elif payload.type == "control" and payload.action in {"back", "skip"}:
        # TODO: implement back/skip behavior if required
        set_thread_state(payload.thread_id, state)
        await get_sse_queue(payload.thread_id).put(
            {
                "event": "step.update",
                "data": {"status": "completed", "step_id": state.current_step.value},
            }
        )
        return {"status": "accepted"}

    agent = get_onboarding_agent()
    q = get_sse_queue(payload.thread_id)

    prev_text = get_last_emitted_text(payload.thread_id)

    async def emit(evt: dict) -> None:
        if isinstance(evt, dict) and evt.get("event") == "token.delta":
            set_last_emitted_text(
                payload.thread_id, evt.get("data", {}).get("text", "")
            )
        await q.put(evt)

    final_state = await agent.process_message_with_events(
        state.user_id, user_text, state, emit
    )

    if not (final_state.last_agent_response or ""):
        text, ensured_state = await agent.process_message(
            state.user_id, user_text, final_state
        )
        final_state = ensured_state
        if text and text != prev_text:
            await q.put({"event": "token.delta", "data": {"text": text}})
            set_last_emitted_text(payload.thread_id, text)

    set_thread_state(payload.thread_id, final_state)

    current_text = get_last_emitted_text(payload.thread_id)
    if current_text == prev_text:
        final_text = final_state.last_agent_response or ""
        if final_text and final_text != prev_text:
            await q.put({"event": "token.delta", "data": {"text": final_text}})
            set_last_emitted_text(payload.thread_id, final_text)

    return {"status": "accepted"}


@router.post("/done/{thread_id}")
async def onboarding_done(thread_id: str) -> dict:
    state = get_thread_state(thread_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    q = get_sse_queue(thread_id)
    await q.put({"event": "onboarding.status", "data": {"status": "processing"}})
    await q.put({"event": "onboarding.status", "data": {"status": "done"}})
    return {"status": "done"}


@router.get("/sse/{thread_id}")
async def onboarding_sse(thread_id: str, request: Request) -> StreamingResponse:
    queue = get_sse_queue(thread_id)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=10.0)
                except TimeoutError:
                    continue

                if isinstance(item, dict) and "event" in item:
                    event_name = item.get("event")
                    payload = item.get("data", {})
                    yield f"event: {event_name}\n"
                    yield f"data: {json.dumps(payload)}\n\n"
                else:
                    yield f"data: {json.dumps(item)}\n\n"
        finally:
            pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")
