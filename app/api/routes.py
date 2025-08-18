from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.app_state import (
    get_sse_queue,
    get_thread_state,
    get_user_sessions,
)
from app.services.onboarding.service import onboarding_service

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


@router.get("/status/{user_id}")
async def get_onboarding_status(user_id: str) -> dict:
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
    result = await onboarding_service.initialize()
    return InitializeResponse(**result)


class MessagePayload(BaseModel):
    thread_id: str
    type: str  # "text" | "choice" | "control"
    text: str | None = None
    step_id: str | None = None
    choice_ids: list[str] | None = None
    action: str | None = None  # "back" | "skip"


@router.post("/message")
async def onboarding_message(payload: MessagePayload) -> dict:
    return await onboarding_service.process_message(
        thread_id=payload.thread_id,
        type=payload.type,
        text=payload.text,
        choice_ids=payload.choice_ids,
        action=payload.action,
    )


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

    async def event_generator() -> AsyncGenerator[str, None]:
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
