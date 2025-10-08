"""Response builder utilities for Goal Agent."""

import json
from typing import Optional

from .constants import ErrorCodes, ResponseKeys


class ResponseBuilder:
    """Builds standardized JSON responses for Goal Agent."""

    @staticmethod
    def success(
        message: str,
        user_id: str,
        goal: Optional[dict] = None,
        goals: Optional[list] = None,
        **extra_fields
    ) -> str:
        """Build a success response.

        Args:
            message: Success message
            user_id: User identifier
            goal: Optional single goal data
            goals: Optional list of goals
            **extra_fields: Additional fields to include

        Returns:
            JSON string response

        """
        response = {
            ResponseKeys.MESSAGE: message,
            ResponseKeys.USER_ID: user_id
        }

        if goal is not None:
            response[ResponseKeys.GOAL] = goal

        if goals is not None:
            response[ResponseKeys.GOALS] = goals

        response.update(extra_fields)
        return json.dumps(response)

    @staticmethod
    def error(
        error_code: str,
        message: str,
        user_id: str,
        goal: Optional[dict] = None,
        goals: Optional[list] = None,
        **extra_fields
    ) -> str:
        """Build an error response.

        Args:
            error_code: Error code from ErrorCodes
            message: Error message
            user_id: User identifier
            goal: Optional goal data
            goals: Optional list of goals
            **extra_fields: Additional fields to include

        Returns:
            JSON string response

        """
        response = {
            ResponseKeys.ERROR: error_code,
            ResponseKeys.MESSAGE: message,
            ResponseKeys.USER_ID: user_id
        }

        if goal is not None:
            response[ResponseKeys.GOAL] = goal
        else:
            response[ResponseKeys.GOAL] = None

        if goals is not None:
            response[ResponseKeys.GOALS] = goals

        response.update(extra_fields)
        return json.dumps(response)

    @staticmethod
    def goal_not_found(user_id: str, context: str = "goal") -> str:
        """Build a goal not found error response."""
        return ResponseBuilder.error(
            error_code=ErrorCodes.GOAL_NOT_FOUND,
            message=f"No {context} found",
            user_id=user_id
        )

    @staticmethod
    def invalid_data(user_id: str, message: str = "Invalid data provided") -> str:
        """Build an invalid data error response."""
        return ResponseBuilder.error(
            error_code=ErrorCodes.INVALID_DATA,
            message=message,
            user_id=user_id
        )

    @staticmethod
    def missing_user_id() -> str:
        """Build a missing user ID error response."""
        return ResponseBuilder.error(
            error_code=ErrorCodes.MISSING_USER_ID,
            message="User ID not found in context",
            user_id="",
            goals=[]
        )
