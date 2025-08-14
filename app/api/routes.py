from __future__ import annotations

from uuid import uuid4
import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.app_state import (
    get_onboarding_agent,
    get_thread_state,
    register_thread,
    set_thread_state,
    get_sse_queue,
)
from app.agents.onboarding import OnboardingState
from app.core.app_state import get_user_sessions

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
    response_text, new_state = await agent.process_message(user_id, "", state)
    set_thread_state(thread_id, new_state)

    await queue.put({"event": "token.delta", "data": {"text": response_text}})
    await queue.put(
        {
            "event": "step.update",
            "data": {"status": "presented", "step_id": new_state.current_step.value},
        }
    )

    return InitializeResponse(
        thread_id=thread_id,
        welcome=response_text,
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
        if payload.action == "back":
            pass
        elif payload.action == "skip":
            pass
        set_thread_state(payload.thread_id, state)
        await get_sse_queue(payload.thread_id).put(
            {
                "event": "step.update",
                "data": {"status": "completed", "step_id": state.current_step.value},
            }
        )
        return {"status": "accepted"}

    agent = get_onboarding_agent()

    await get_sse_queue(payload.thread_id).put(
        {
            "event": "step.update",
            "data": {"status": "validating", "step_id": state.current_step.value},
        }
    )

    prev_completed = set(s.value for s in state.completed_steps)
    response_text, new_state = await agent.process_message(
        state.user_id, user_text, state
    )
    set_thread_state(payload.thread_id, new_state)

    q = get_sse_queue(payload.thread_id)
    await q.put({"event": "token.delta", "data": {"text": response_text}})

    new_completed = set(s.value for s in new_state.completed_steps)
    for step_value in sorted(new_completed - prev_completed):
        await q.put(
            {
                "event": "step.update",
                "data": {"status": "completed", "step_id": step_value},
            }
        )

    await q.put(
        {
            "event": "step.update",
            "data": {"status": "presented", "step_id": new_state.current_step.value},
        }
    )

    if new_state.ready_for_completion and new_state.user_context.ready_for_orchestrator:
        await q.put({"event": "onboarding.status", "data": {"status": "done"}})

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
                except asyncio.TimeoutError:
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
