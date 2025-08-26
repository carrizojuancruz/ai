from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.app_state import get_sse_queue
from app.services.guest.service import guest_service

router = APIRouter(prefix="/guest", tags=["Guest"])


class InitializeResponse(BaseModel):
    thread_id: str
    welcome: dict
    sse_url: str


@router.post("/initialize", response_model=InitializeResponse)
async def initialize_guest() -> InitializeResponse:
    result = await guest_service.initialize()
    return InitializeResponse(**result)


class MessagePayload(BaseModel):
    thread_id: str
    text: str


@router.post("/message")
async def guest_message(payload: MessagePayload) -> dict:
    return await guest_service.process_message(thread_id=payload.thread_id, text=payload.text)


@router.get("/sse/{thread_id}")
async def guest_sse(thread_id: str, request: Request) -> StreamingResponse:
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
