from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.app_state import (
    get_onboarding_status_for_user,
    get_sse_queue,
    get_thread_state,
)
from app.services.onboarding.service import onboarding_service

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


@router.get("/status/{user_id}")
async def get_onboarding_status(user_id: str) -> dict:
    try:
        uid = UUID(user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid user_id") from e

    status = get_onboarding_status_for_user(uid)

    if not status.get("active") and not status.get("onboarding_done"):
        try:
            from app.models import UserContext
            from app.services.external_context.user.mapping import map_ai_context_to_user_context
            from app.services.external_context.user.repository import ExternalUserRepository

            repo = ExternalUserRepository()
            data = await repo.get_by_id(uid)
            if data:
                ctx = UserContext(user_id=uid)
                map_ai_context_to_user_context(data, ctx)
                if ctx.ready_for_orchestrator:
                    status = {
                        "active": False,
                        "onboarding_done": True,
                        "thread_id": None,
                        "current_flow_step": None,
                    }
        except Exception:
            pass

    return status


class InitializePayload(BaseModel):
    user_id: str | None = None
    show_complete_welcome_message: bool = True


class InitializeResponse(BaseModel):
    thread_id: str
    welcome: str
    sse_url: str


@router.post("/initialize", response_model=InitializeResponse)
async def initialize_onboarding(payload: InitializePayload) -> InitializeResponse:
    result = await onboarding_service.initialize(
        user_id=payload.user_id,
        show_complete_welcome_message=payload.show_complete_welcome_message,
    )
    return InitializeResponse(**result)


class MessagePayload(BaseModel):
    thread_id: str
    type: str
    text: str | None = None
    step_id: str | None = None
    choice_ids: list[str] | None = None
    action: str | None = None


@router.post("/message")
async def onboarding_message(payload: MessagePayload) -> dict:
    if payload.type == "choice" and not payload.choice_ids:
        raise HTTPException(status_code=400, detail="choice_ids required for type 'choice'")
    if payload.type == "text" and payload.text is None:
        raise HTTPException(status_code=400, detail="text required for type 'text'")

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

    await onboarding_service.finalize(thread_id=thread_id)

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
            # Clean up SSE queue when client disconnects
            from app.core.app_state import drop_sse_queue
            drop_sse_queue(thread_id)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
