from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

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


class SupervisorConfirmPayload(BaseModel):
    thread_id: str = Field(..., description="Thread ID of the conversation")
    decision: dict[str, Any] | str | bool = Field(
        ...,
        description="Decision payload. Can be a boolean, string, or dict with 'action' and/or 'draft' fields.",
        examples=[
            # Approve (simple boolean)
            True,
            # Approve (string)
            "approve",
            # Cancel (boolean)
            False,
            # Cancel (dict with action)
            {"action": "cancel"},
            # Approve (dict with approved field)
            {"approved": True},
            # Edit with draft updates (dict with draft field)
            {
                "action": "edit",
                "draft": {
                    "name": "Updated Car Name",
                    "estimated_value": "40000.0",
                    "category": "Vehicles"
                }
            },
            # Edit with only draft (action inferred)
            {
                "draft": {
                    "name": "Updated Car Name",
                    "estimated_value": "40000.0"
                }
            }
        ]
    )
    confirm_id: str = Field(..., description="Confirmation ID from the confirm.request event. Required to match the response to the correct confirmation request.")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "thread_id": "a3384d17-501b-44d5-9715-61824781e1b6",
                    "confirm_id": "b98ce4fe-c61c-4597-b4c7-df5c7993eaa9",
                    "decision": True
                },
                {
                    "thread_id": "a3384d17-501b-44d5-9715-61824781e1b6",
                    "confirm_id": "b98ce4fe-c61c-4597-b4c7-df5c7993eaa9",
                    "decision": "approve"
                },
                {
                    "thread_id": "a3384d17-501b-44d5-9715-61824781e1b6",
                    "confirm_id": "b98ce4fe-c61c-4597-b4c7-df5c7993eaa9",
                    "decision": False
                },
                {
                    "thread_id": "a3384d17-501b-44d5-9715-61824781e1b6",
                    "confirm_id": "b98ce4fe-c61c-4597-b4c7-df5c7993eaa9",
                    "decision": {"approved": False}
                },
                {
                    "thread_id": "a3384d17-501b-44d5-9715-61824781e1b6",
                    "confirm_id": "b98ce4fe-c61c-4597-b4c7-df5c7993eaa9",
                    "decision": {
                        "action": "cancel"
                    }
                },
                {
                    "thread_id": "a3384d17-501b-44d5-9715-61824781e1b6",
                    "confirm_id": "b98ce4fe-c61c-4597-b4c7-df5c7993eaa9",
                    "decision": {
                        "action": "edit",
                        "draft": {
                            "name": "Updated Car Name",
                            "estimated_value": "45000.0"
                        }
                    }
                },
                {
                    "thread_id": "a3384d17-501b-44d5-9715-61824781e1b6",
                    "confirm_id": "b98ce4fe-c61c-4597-b4c7-df5c7993eaa9",
                    "decision": {
                        "draft": {
                            "name": "Updated Name",
                            "estimated_value": "50000.0"
                        }
                    }
                }
            ]
        }


@router.post("/confirm")
async def supervisor_confirm(payload: SupervisorConfirmPayload) -> dict:
    """Resume an interrupted confirmation flow with a user decision.

    This endpoint resumes a paused graph execution after a confirm.request event.

    **Required Fields:**
        - `thread_id`: The conversation thread ID
        - `confirm_id`: The confirmation ID from the confirm.request event (required to match the response to the correct confirmation)
        - `decision`: The user's decision (see formats below)

    **Decision Formats:**
        - Boolean: `True` to approve, `False` to cancel
        - String: `"approve"`, `"cancel"`, `"edit"`, etc.
        - Dict with optional fields:
            * `"action"`: `"approve"` | `"cancel"` | `"edit"`
            * `"approved"`: boolean (alternative to action)
            * `"draft"`: dict with updated fields (for edits)

    When editing, include a `"draft"` object with the fields you want to update.
    The system will merge these changes with the existing draft and re-validate.

    **Examples:**

        Approve (boolean):
        ```json
        {
            "thread_id": "a3384d17-501b-44d5-9715-61824781e1b6",
            "confirm_id": "b98ce4fe-c61c-4597-b4c7-df5c7993eaa9",
            "decision": true
        }
        ```

        Approve (string):
        ```json
        {
            "thread_id": "a3384d17-501b-44d5-9715-61824781e1b6",
            "confirm_id": "b98ce4fe-c61c-4597-b4c7-df5c7993eaa9",
            "decision": "approve"
        }
        ```

        Cancel (boolean):
        ```json
        {
            "thread_id": "a3384d17-501b-44d5-9715-61824781e1b6",
            "confirm_id": "b98ce4fe-c61c-4597-b4c7-df5c7993eaa9",
            "decision": false
        }
        ```

        Cancel (dict):
        ```json
        {
            "thread_id": "a3384d17-501b-44d5-9715-61824781e1b6",
            "confirm_id": "b98ce4fe-c61c-4597-b4c7-df5c7993eaa9",
            "decision": {"action": "cancel"}
        }
        ```

        Edit with updates:
        ```json
        {
            "thread_id": "a3384d17-501b-44d5-9715-61824781e1b6",
            "confirm_id": "b98ce4fe-c61c-4597-b4c7-df5c7993eaa9",
            "decision": {
                "action": "edit",
                "draft": {
                    "name": "Updated Name",
                    "estimated_value": "45000.0"
                }
            }
        }
        ```

        Edit (draft only, action inferred):
        ```json
        {
            "thread_id": "a3384d17-501b-44d5-9715-61824781e1b6",
            "confirm_id": "b98ce4fe-c61c-4597-b4c7-df5c7993eaa9",
            "decision": {
                "draft": {
                    "name": "Updated Name",
                    "estimated_value": "50000.0"
                }
            }
        }
        ```

    """
    await supervisor_service.resume_interrupt(thread_id=payload.thread_id, decision=payload.decision, confirm_id=payload.confirm_id)
    return {"status": "resumed"}


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
