from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.core.config import config
from app.observability.logging_config import get_logger
from app.services.nudges.activity_counter import get_activity_counter
from app.services.nudges.evaluator import get_nudge_evaluator, iter_active_users
from app.services.queue import get_sqs_manager

logger = get_logger(__name__)
router = APIRouter(prefix="/nudges", tags=["nudges"])


class EvaluateRequest(BaseModel):
    """Request to evaluate nudges."""

    nudge_type: str = Field(..., description="Type of nudge: static_bill, memory_icebreaker, or info_based")
    nudge_id: Optional[str] = Field(None, description="For info_based nudges, the specific nudge ID")
    notification_text: Optional[str] = Field(None, description="For info_based nudges, FOS-provided notification text")
    preview_text: Optional[str] = Field(None, description="For info_based nudges, FOS-provided preview text")


class EvaluateResponse(BaseModel):
    """Response from nudge evaluation."""

    status: str
    message: str
    task_id: Optional[str] = None


class ManualTriggerRequest(BaseModel):
    """Request to manually trigger a nudge for a user."""

    user_id: UUID
    nudge_type: str
    force: bool = False
    priority_override: Optional[int] = None


class UserStatusResponse(BaseModel):
    """User's nudge status."""

    user_id: UUID
    nudges_today: int
    nudges_this_week: int
    last_nudge: Optional[str] = None
    next_eligible: Optional[str] = None
    in_cooldown: bool = False
    queued_nudges: int = 0


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate_nudges(request: EvaluateRequest, background_tasks: BackgroundTasks) -> EvaluateResponse:
    try:
        logger.info(
            "nudge_eval.request",
            nudge_type=request.nudge_type,
            nudge_id=request.nudge_id,
            has_text=bool(request.notification_text),
        )

        if request.nudge_type == "info_based":
            if not all([request.nudge_id, request.notification_text, request.preview_text]):
                raise HTTPException(
                    status_code=400, detail="info_based nudges require nudge_id, notification_text, and preview_text"
                )

        if not config.NUDGES_ENABLED:
            return EvaluateResponse(status="skipped", message="Nudges are currently disabled")

        import uuid

        task_id = str(uuid.uuid4())

        background_tasks.add_task(
            _evaluate_all_users,
            task_id,
            request.nudge_type,
            request.nudge_id,
            request.notification_text,
            request.preview_text,
        )

        return EvaluateResponse(
            status="started", message=f"Evaluation started for {request.nudge_type} nudges", task_id=task_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("nudge_eval.failed", nudge_type=request.nudge_type, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to start evaluation: {str(e)}") from e


@router.post("/trigger", response_model=Dict[str, Any])
async def trigger_nudge_manual(request: ManualTriggerRequest) -> Dict[str, Any]:
    try:
        evaluator = get_nudge_evaluator()

        if request.force:
            logger.warning("nudge_eval.manual_force", user_id=str(request.user_id), nudge_type=request.nudge_type)

        result = await evaluator._evaluate_single_user(user_id=request.user_id, nudge_type=request.nudge_type)

        if request.priority_override and result["status"] == "queued":
            result["priority_override"] = request.priority_override

        return result

    except Exception as e:
        logger.error(
            "nudge_eval.manual_trigger_failed",
            user_id=str(request.user_id),
            nudge_type=request.nudge_type,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Failed to trigger nudge: {str(e)}") from e


@router.get("/status/{user_id}", response_model=UserStatusResponse)
async def get_user_nudge_status(user_id: UUID) -> UserStatusResponse:
    try:
        activity_counter = get_activity_counter()
        sqs_manager = get_sqs_manager()

        stats = await activity_counter.get_nudge_stats(user_id)

        in_cooldown = False
        for nudge_type in ["static_bill", "memory_icebreaker", "info_based"]:
            if await activity_counter.is_in_cooldown(user_id, nudge_type):
                in_cooldown = True
                break

        queue_depth = await sqs_manager.get_queue_depth()

        from datetime import datetime, timedelta

        next_eligible = None
        if stats.nudges_today >= config.NUDGE_MAX_PER_DAY:
            tomorrow = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            next_eligible = tomorrow.isoformat()
        elif in_cooldown:
            next_eligible = (datetime.now() + timedelta(days=config.NUDGE_MEMORY_COOLDOWN_DAYS)).isoformat()

        return UserStatusResponse(
            user_id=user_id,
            nudges_today=stats.nudges_today,
            nudges_this_week=stats.nudges_this_week,
            last_nudge=stats.last_nudge.isoformat() if stats.last_nudge else None,
            next_eligible=next_eligible,
            in_cooldown=in_cooldown,
            queued_nudges=min(queue_depth, 10),
        )

    except Exception as e:
        logger.error("nudge_eval.status_failed", user_id=str(user_id), error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get user status: {str(e)}") from e


@router.get("/health", response_model=Dict[str, Any])
async def get_nudge_health() -> Dict[str, Any]:
    try:
        sqs_manager = get_sqs_manager()
        queue_depth = await sqs_manager.get_queue_depth()

        return {
            "status": "healthy",
            "nudges_enabled": config.NUDGES_ENABLED,
            "queue_depth": queue_depth,
            "queue_url": config.SQS_QUEUE_URL,
            "rate_limits": {"max_per_day": config.NUDGE_MAX_PER_DAY, "max_per_week": config.NUDGE_MAX_PER_WEEK},
        }

    except Exception as e:
        logger.error("nudge_eval.health_check_failed", error=str(e))
        return {"status": "unhealthy", "error": str(e)}


async def _evaluate_all_users(
    task_id: str,
    nudge_type: str,
    nudge_id: Optional[str],
    notification_text: Optional[str],
    preview_text: Optional[str],
) -> None:
    try:
        logger.info("nudge_eval.background_started", task_id=task_id, nudge_type=nudge_type, nudge_id=nudge_id)

        evaluator = get_nudge_evaluator()
        total_evaluated = 0
        total_queued = 0
        total_skipped = 0

        async for user_page in iter_active_users():
            logger.info("nudge_eval.processing_page", task_id=task_id, page_size=len(user_page))

            result = await evaluator.evaluate_nudges_batch(
                user_ids=user_page,
                nudge_type=nudge_type,
                nudge_id=nudge_id,
                notification_text=notification_text,
                preview_text=preview_text,
            )

            total_evaluated += result["evaluated"]
            total_queued += result["queued"]
            total_skipped += result["skipped"]

        logger.info(
            "nudge_eval.background_complete",
            task_id=task_id,
            nudge_type=nudge_type,
            total_evaluated=total_evaluated,
            total_queued=total_queued,
            total_skipped=total_skipped,
        )

    except Exception as e:
        logger.error("nudge_eval.background_failed", task_id=task_id, nudge_type=nudge_type, error=str(e))
        raise
