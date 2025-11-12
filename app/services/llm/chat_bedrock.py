"""Wrapper for AWS Bedrock ChatBedrockConverse."""

from __future__ import annotations

import logging
from typing import Any

from botocore.exceptions import ClientError
from langchain_aws import ChatBedrockConverse
from tenacity import RetryCallState, retry, retry_if_exception, stop_after_attempt

from app.core.config import config

logger = logging.getLogger(__name__)


def _is_retryable_validation_error(exception: BaseException) -> bool:
    """Check if exception is a retryable ValidationException from Bedrock."""
    if not isinstance(exception, ClientError):
        return False

    error_code = exception.response.get("Error", {}).get("Code", "")
    error_message = exception.response.get("Error", {}).get("Message", "")

    if error_code == "ValidationException" and "validation_error" in error_message:
        logger.info(
            f"Retryable ValidationException detected: {error_message[:200]}"
        )
        return True

    return False


def _log_retry(retry_state: RetryCallState) -> None:
    """Log retry attempts before sleep."""
    logger.warning(
        f"Bedrock retry attempt {retry_state.attempt_number}/{config.BEDROCK_RETRY_MAX_ATTEMPTS} "
        f"after error: {retry_state.outcome.exception()}"
    )


_bedrock_retry = retry(
    stop=stop_after_attempt(config.BEDROCK_RETRY_MAX_ATTEMPTS),
    retry=retry_if_exception(_is_retryable_validation_error),
    before_sleep=_log_retry,
)


class ChatBedrock(ChatBedrockConverse):
    """ChatBedrockConverse with automatic retry on transient errors."""

    @_bedrock_retry
    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        """Invoke with automatic retry on ClientError."""
        return super().invoke(*args, **kwargs)

    @_bedrock_retry
    async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        """Async invoke with automatic retry on ClientError."""
        return await super().ainvoke(*args, **kwargs)

