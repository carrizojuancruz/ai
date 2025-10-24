import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

_instance: Optional['FeedbackService'] = None
_lock = threading.Lock()


class FeedbackService:
    """Service for handling user feedback submissions to Langfuse."""

    def __init__(self):
        """Initialize the feedback service."""
        self._initialize_client()

    @classmethod
    def get_instance(cls) -> 'FeedbackService':
        """Get thread-safe singleton instance of the feedback service."""
        global _instance, _lock

        if _instance is None:
            with _lock:
                if _instance is None:
                    _instance = cls()
        return _instance

    def _initialize_client(self):
        """Initialize Langfuse client for scoring."""
        from .langfuse.config import LangfuseConfig

        config = LangfuseConfig.from_env_supervisor()

        from langfuse import Langfuse

        self.client = Langfuse(
            public_key=config.public_key,
            secret_key=config.secret_key,
            host=config.host
        )

        logger.info("FeedbackService initialized with Langfuse SDK client")

    async def submit_feedback(
        self,
        *,
        thread_id: str,
        is_positive: bool,
        comment: str | None = None,
        user_id: str | None = None
    ) -> str:
        """Submit user feedback to Langfuse using SDK.

        Args:
            thread_id: The conversation thread identifier
            is_positive: True for thumbs up, False for thumbs down
            comment: Optional text feedback from the user
            user_id: Optional user identifier for additional context

        Returns:
            feedback_id: Unique identifier for the feedback record

        Raises:
            Exception: If feedback submission fails

        """
        try:
            feedback_id = f"feedback_{thread_id}"
            if user_id:
                feedback_id = f"feedback_{thread_id}_{user_id}"

            value = 1 if is_positive else 0

            self.client.score.create(
                name="user_feedback",
                value=value,
                traceId=thread_id,
                dataType="BOOLEAN",
                comment=comment.strip() if comment and comment.strip() else None,
                id=feedback_id
            )

            # Flush to ensure the score is sent
            self.client.flush()

            logger.info(
                f"Feedback submitted successfully: thread_id={thread_id}, "
                f"is_positive={is_positive}, feedback_id={feedback_id}"
            )

            return feedback_id

        except Exception as e:
            logger.error(f"Failed to submit feedback for thread {thread_id}: {e}")
            raise Exception(f"Failed to submit feedback: {str(e)}") from e


# Convenience function to get the feedback service instance
def get_feedback_service() -> FeedbackService:
    """Get the singleton feedback service instance."""
    return FeedbackService.get_instance()


# Global feedback service instance for import convenience
feedback_service = get_feedback_service()
