from __future__ import annotations

import logging
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.repositories.s3_vectors_store import get_s3_vectors_store
from app.services.external_context.notifications import NotificationsClient
from app.services.nudges.selector import NudgeSelector, update_memory_cooldown
from app.services.nudges.templates import NudgeType
from app.services.supervisor import SupervisorService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nudges", tags=["Nudges"])


class BillPayload(BaseModel):
    label: str
    due_date: str
    amount: float = 0.0


class NudgeInitRequest(BaseModel):
    type: Literal["static_bill", "memory_icebreaker", "info_based"]
    user_id: UUID
    channel: Literal["push", "in_app"] = "push"
    rule_id: Optional[str] = None
    bill: Optional[BillPayload] = None


class NudgeInitResponse(BaseModel):
    thread_id: str
    status: Literal["enqueued", "skipped"]
    message: Optional[str] = None
    preview_text: Optional[str] = None


@router.post("/init", response_model=NudgeInitResponse)
async def initialize_nudge(request: NudgeInitRequest) -> NudgeInitResponse:
    try:
        logger.info(
            "nudge.init.request",
            extra={
                "user_id": str(request.user_id),
                "type": request.type,
                "channel": request.channel,
                "rule_id": request.rule_id,
            },
        )

        s3_vectors_store = get_s3_vectors_store()
        selector = NudgeSelector(s3_vectors_store)
        supervisor_service = SupervisorService()
        notifications_client = NotificationsClient()

        payload = None
        if request.type == "static_bill" and request.bill:
            payload = {"bill": request.bill.model_dump(), "channel": request.channel}

        user_context = None
        if request.type == "info_based":
            try:
                ctx = await supervisor_service._load_user_context_from_external(request.user_id)
                user_context = ctx.model_dump(mode="json") if ctx else {}
            except Exception as e:
                logger.warning(f"Failed to load user context for nudge: {e}")
                user_context = {}

        nudge_type = NudgeType(request.type)
        selection = await selector.select_nudge(
            user_id=request.user_id,
            nudge_type=nudge_type,
            rule_id=request.rule_id,
            payload=payload,
            user_context=user_context,
        )

        if not selection:
            logger.info(
                "nudge.init.skipped",
                extra={
                    "user_id": str(request.user_id),
                    "reason": "no_eligible_candidates",
                },
            )
            return NudgeInitResponse(thread_id="", status="skipped", message="No eligible nudge candidates found")

        result = await supervisor_service.initialize_nudge(
            user_id=request.user_id,
            nudge_prompt_line=selection.nudge_prompt_line,
            preview_text=selection.preview_text,
            channel=selection.channel.value,
        )

        thread_id = result["thread_id"]

        notification_sent = await notifications_client.create_notification(
            user_id=request.user_id,
            thread_id=thread_id,
            channel=selection.channel.value,
            preview_text=selection.preview_text,
            metadata={
                "nudge_type": request.type,
                "rule_id": selection.rule_id,
            },
        )

        if not notification_sent:
            logger.warning(
                "nudge.notification.failed",
                extra={
                    "user_id": str(request.user_id),
                    "thread_id": thread_id,
                },
            )

        if selection.memory_key and nudge_type == NudgeType.MEMORY_ICEBREAKER:
            await update_memory_cooldown(
                s3_vectors_store,
                request.user_id,
                selection.memory_key,
                cooldown_days=7,
            )

        logger.info(
            "nudge.init.success",
            extra={
                "user_id": str(request.user_id),
                "thread_id": thread_id,
                "rule_id": selection.rule_id,
                "preview_text_hash": hash(selection.preview_text),
            },
        )

        return NudgeInitResponse(
            thread_id=thread_id, status="enqueued", message=result.get("message"), preview_text=selection.preview_text
        )

    except Exception as e:
        logger.error(
            "nudge.init.error",
            extra={
                "user_id": str(request.user_id),
                "error": str(e),
            },
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Failed to initialize nudge: {str(e)}") from e


@router.get("/health")
async def nudges_health() -> dict[str, str]:
    return {"status": "healthy", "service": "nudges"}
