from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents.supervisor.memory.icebreaker_consumer import debug_icebreaker_flow
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
    voice: bool = False  # Optional parameter


@router.post("/initialize", response_model=SupervisorInitializeResponse)
async def initialize_supervisor(payload: SupervisorInitializePayload) -> SupervisorInitializeResponse:
    result = await supervisor_service.initialize(
        user_id=payload.user_id,
        voice=payload.voice,
    )
    return SupervisorInitializeResponse(**result)


class SupervisorMessagePayload(BaseModel):
    thread_id: str
    text: str
    voice: bool = True


@router.post("/message")
async def supervisor_message(payload: SupervisorMessagePayload) -> dict:
    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=400, detail="Message text must not be empty")
    await supervisor_service.process_message(thread_id=payload.thread_id, text=payload.text, voice=payload.voice)
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
            from app.core.app_state import drop_sse_queue

            drop_sse_queue(thread_id)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/debug/icebreaker/{user_id}")
async def debug_icebreaker(user_id: str) -> dict:
    try:
        result = await debug_icebreaker_flow(user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Debug failed: {str(e)}") from e


@router.post("/debug/test-icebreaker")
async def test_icebreaker_flow(payload: SupervisorInitializePayload) -> dict:
    try:
        from app.services.supervisor import supervisor_service

        result = await supervisor_service.initialize(user_id=payload.user_id)

        return {
            "status": "success",
            "thread_id": result["thread_id"],
            "welcome": result["welcome"],
            "message": "Check logs for icebreaker processing details",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}") from e
