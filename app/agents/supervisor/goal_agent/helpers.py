import logging
from typing import Any, Optional
from uuid import UUID

from langgraph.types import Command

logger = logging.getLogger(__name__)


def create_error_command(error_message: str) -> Command:
    from app.agents.supervisor.handoff import create_handoff_back_messages

    handoff_messages = create_handoff_back_messages("goal_agent", "supervisor")
    return Command(
        update={
            "messages": [
                {"role": "assistant", "content": error_message, "name": "goal_agent"},
                handoff_messages[0],
            ]
        },
        goto="supervisor",
    )

def get_last_user_message_text(messages: list[Any]) -> str:
    for msg in reversed(messages):
        if hasattr(msg, "content") and hasattr(msg, "type") and msg.type == "human":
            return str(msg.content)
    return ""

def get_user_id_from_messages(messages: list[Any]) -> UUID | None:
    return None


def extract_goal_id(data) -> Optional[str]:
    """Extract goal_id from various data formats.

    Args:
        data: Data object or dict containing goal_id

    Returns:
        goal_id as string, or None if not found

    """
    if hasattr(data, 'goal_id'):
        return str(data.goal_id)
    elif isinstance(data, dict):
        goal_id = data.get('goal_id')
        if goal_id:
            return str(goal_id)
    return None


def extract_goal_from_response(response: Optional[dict]) -> Optional[dict]:
    """Extract goal data from API response.

    Args:
        response: API response dict

    Returns:
        Goal dict or None if not found

    """
    if not response or not response.get('goal'):
        return None
    return response.get('goal')


def get_all_status_values(status_enum) -> list[str]:
    """Get all status values from a status enum.

    Args:
        status_enum: Enum class containing status values

    Returns:
        List of status values as strings

    """
    return [status.value for status in status_enum]

