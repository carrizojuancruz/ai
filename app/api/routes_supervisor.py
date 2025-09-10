from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.app_state import get_sse_queue
from app.services.supervisor import supervisor_service

router = APIRouter(prefix="/supervisor", tags=["Supervisor"])


class SupervisorInitializeResponse(BaseModel):
    thread_id: str
    welcome: str
    sse_url: str
    prior_conversation_summary: str | None = None


class SupervisorInitializePayload(BaseModel):
    user_id: UUID


@router.post("/initialize", response_model=SupervisorInitializeResponse)
async def initialize_supervisor(payload: SupervisorInitializePayload) -> SupervisorInitializeResponse:
    result = await supervisor_service.initialize(user_id=payload.user_id)
    return SupervisorInitializeResponse(**result)


class SupervisorMessagePayload(BaseModel):
    thread_id: str
    text: str


@router.post("/message")
async def supervisor_message(payload: SupervisorMessagePayload) -> dict:
    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=400, detail="Message text must not be empty")
    await supervisor_service.process_message(thread_id=payload.thread_id, text=payload.text)
    return {"status": "accepted"}


@router.get("/sse/{thread_id}")
async def supervisor_sse(thread_id: str, request: Request) -> StreamingResponse:
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


