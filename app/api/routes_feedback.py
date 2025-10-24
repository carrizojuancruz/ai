from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.feedback import feedback_service

router = APIRouter(prefix="/feedback", tags=["Feedback"])


class UserFeedbackPayload(BaseModel):
    """Request model for user feedback submission.

    Feedback is stored as BOOLEAN scores (1 for thumbs up, 0 for thumbs down)
    following Langfuse's recommended pattern for binary feedback.
    """

    thread_id: str
    is_positive: bool
    comment: str | None = None

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "thread_id": "abc-123-def-456",
                    "is_positive": True,
                    "comment": "This response was very helpful!"
                },
                {
                    "thread_id": "xyz-789-abc-123",
                    "is_positive": False,
                    "comment": "The answer wasn't quite what I was looking for"
                },
                {
                    "thread_id": "simple-thread-456",
                    "is_positive": True,
                    "comment": None
                }
            ]
        }


class UserFeedbackResponse(BaseModel):
    """Response model for feedback submission."""

    status: str
    message: str
    feedback_id: str | None = None

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "status": "success",
                    "message": "Feedback recorded successfully",
                    "feedback_id": "feedback_abc-123-def-456_user123"
                },
                {
                    "status": "error",
                    "message": "Failed to record feedback",
                    "feedback_id": None
                }
            ]
        }


@router.post("/submit", response_model=UserFeedbackResponse)
async def submit_user_feedback(payload: UserFeedbackPayload) -> UserFeedbackResponse:
    """Submit user feedback for a conversation thread.

    This endpoint allows users to provide thumbs up/down feedback on AI responses
    with optional text comments. The feedback is recorded in Langfuse for analysis
    and improvement of the AI system.

    Args:
        payload: The feedback payload containing thread_id, is_positive flag, and optional comment

    Returns:
        UserFeedbackResponse: Response containing status, message, and feedback_id

    """
    try:
        feedback_id = await feedback_service.submit_feedback(
            thread_id=payload.thread_id,
            is_positive=payload.is_positive,
            comment=payload.comment
        )

        return UserFeedbackResponse(
            status="success",
            message="Feedback recorded successfully",
            feedback_id=feedback_id
        )

    except Exception as e:
        # Log the error but don't expose internal details
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to submit feedback: {e}")

        raise HTTPException(
            status_code=500,
            detail="Failed to record feedback. Please try again later."
        ) from e
