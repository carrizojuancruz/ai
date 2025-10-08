"""Constants and error codes for Goal Agent."""


class ResponseKeys:
    """Standard keys used in JSON responses."""

    ERROR = "error"
    MESSAGE = "message"
    GOAL = "goal"
    GOALS = "goals"
    USER_ID = "user_id"
    COUNT = "count"
    CURRENT_STATUS = "current_status"
    ATTEMPTED_STATUS = "attempted_status"
    VALID_TRANSITIONS = "valid_transitions"
    PREVIOUS_STATUS = "previous_status"
    NEW_STATUS = "new_status"
    MISSING_FIELDS = "missing_fields"
    PROCESSED_DATA = "processed_data"


class ErrorCodes:
    """Standard error codes for Goal Agent operations."""

    INVALID_DATA = "INVALID_DATA"
    NO_GOAL_TO_UPDATE = "NO_GOAL_TO_UPDATE"
    NO_GOAL_TO_DELETE = "NO_GOAL_TO_DELETE"
    NO_GOAL_TO_SWITCH = "NO_GOAL_TO_SWITCH"
    MISSING_USER_ID = "MISSING_USER_ID"
    MISSING_REQUIRED_FIELDS = "MISSING_REQUIRED_FIELDS"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    CREATE_FAILED = "CREATE_FAILED"
    UPDATE_FAILED = "UPDATE_FAILED"
    DELETE_FAILED = "DELETE_FAILED"
    SWITCH_FAILED = "SWITCH_FAILED"
    READ_FAILED = "READ_FAILED"
    GOAL_NOT_FOUND = "GOAL_NOT_FOUND"
    USER_HAS_NO_IN_PROGRESS_GOALS = "USER_HAS_NO_IN_PROGRESS_GOALS"
    INVALID_STATUS = "INVALID_STATUS"
    INVALID_TRANSITION = "INVALID_TRANSITION"
    INVALID_GOAL_STATE = "INVALID_GOAL_STATE"
