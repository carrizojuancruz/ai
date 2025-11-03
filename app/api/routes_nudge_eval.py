from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.core.config import config
from app.observability.logging_config import get_logger
from app.services.nudges.evaluator import get_nudge_evaluator, iter_active_users
from app.services.queue import get_sqs_manager

logger = get_logger(__name__)
router = APIRouter(prefix="/nudges", tags=["Nudges"])


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


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate_nudges(request: EvaluateRequest, background_tasks: BackgroundTasks) -> EvaluateResponse:
    try:
        logger.info(
            f"nudge_eval.request: nudge_type={request.nudge_type}, "
            f"nudge_id={request.nudge_id}, has_text={bool(request.notification_text)}"
        )

        if request.nudge_type == "info_based" and not all(
            [request.nudge_id, request.notification_text, request.preview_text]
        ):
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
        logger.error(f"nudge_eval.failed: {str(e)} (nudge_type={request.nudge_type})")
        raise HTTPException(status_code=500, detail=f"Failed to start evaluation: {str(e)}") from e


@router.post("/trigger", response_model=Dict[str, Any])
async def trigger_nudge_manual(request: ManualTriggerRequest) -> Dict[str, Any]:
    try:
        evaluator = get_nudge_evaluator()

        if request.force:
            logger.warning(f"nudge_eval.manual_force: user_id={str(request.user_id)}, nudge_type={request.nudge_type}")

        # Consistent behavior for ALL nudge types
        batch_result = await evaluator.evaluate_nudges_batch(
            user_ids=[str(request.user_id)], nudge_type=request.nudge_type
        )

        if batch_result.get("results"):
            result = batch_result["results"][0]
            if request.priority_override and result.get("status") == "queued":
                result["priority_override"] = request.priority_override
            return result
        else:
            return {"user_id": str(request.user_id), "status": "error", "reason": "No evaluation result returned"}

    except Exception as e:
        logger.error(
            f"nudge_eval.manual_trigger_failed: user_id={str(request.user_id)}, "
            f"nudge_type={request.nudge_type}, error={str(e)}"
        )
        raise HTTPException(status_code=500, detail=f"Failed to trigger nudge: {str(e)}") from e


@router.get("/health", response_model=Dict[str, Any])
async def get_nudge_health() -> Dict[str, Any]:
    try:
        sqs_manager = get_sqs_manager()
        queue_depth = await sqs_manager.get_queue_depth()

        return {
            "status": "healthy",
            "nudges_enabled": config.NUDGES_ENABLED,
            "queue_depth": queue_depth,
            "queue_url": config.SQS_NUDGES_AI_INFO_BASED,
        }

    except Exception as e:
        logger.error(f"nudge_eval.health_check_failed: {str(e)}")
        return {"status": "unhealthy", "error": str(e)}


async def _evaluate_all_users(
    task_id: str,
    nudge_type: str,
    nudge_id: Optional[str],
    notification_text: Optional[str],
    preview_text: Optional[str],
) -> None:
    try:
        logger.info(f"nudge_eval.background_started: task_id={task_id}, nudge_type={nudge_type}, nudge_id={nudge_id}")

        evaluator = get_nudge_evaluator()
        total_evaluated = 0
        total_queued = 0
        total_skipped = 0

        async for user_page in iter_active_users():
            logger.info(f"nudge_eval.processing_page: task_id={task_id}, page_size={len(user_page)}")

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
            f"nudge_eval.background_complete: task_id={task_id}, nudge_type={nudge_type}, "
            f"total_evaluated={total_evaluated}, total_queued={total_queued}, "
            f"total_skipped={total_skipped}"
        )

    except Exception as e:
        logger.error(f"nudge_eval.background_failed: {str(e)} (task_id={task_id}, nudge_type={nudge_type})")
        raise
