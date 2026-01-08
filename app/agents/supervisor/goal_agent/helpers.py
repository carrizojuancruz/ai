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
    if hasattr(data, "goal_id"):
        return str(data.goal_id)
    elif isinstance(data, dict):
        goal_id = data.get("goal_id")
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
    if not response or not response.get("goal"):
        return None
    return response.get("goal")


def get_all_status_values(status_enum) -> list[str]:
    """Get all status values from a status enum.

    Args:
        status_enum: Enum class containing status values

    Returns:
        List of status values as strings

    """
    return [status.value for status in status_enum]


def format_goal_reminder_info(goal_data: dict) -> str:
    """Format reminder information safely, preventing hallucination.

    This function explicitly checks for reminder existence and only formats
    actual reminder data from the goal object. It prevents the LLM from
    fabricating reminder times when none exist.

    Args:
        goal_data: Goal dictionary containing all goal fields

    Returns:
        Formatted reminder string or "No reminders configured." if absent

    Examples:
        >>> goal_data = {"reminders": None}
        >>> format_goal_reminder_info(goal_data)
        'No reminders configured.'

        >>> goal_data = {"reminders": {"items": []}}
        >>> format_goal_reminder_info(goal_data)
        'No reminders configured.'

        >>> goal_data = {"reminders": {"items": [{"schedule": {"type": "recurring", "unit": "week", "weekdays": ["mon", "wed"], "time_of_day": "09:00"}}]}}
        >>> format_goal_reminder_info(goal_data)
        'Reminders: Recurring weekly on mon, wed at 09:00'

    """
    reminders = goal_data.get("reminders")

    if reminders is None or not isinstance(reminders, dict):
        return "No reminders configured."

    items = reminders.get("items", [])
    if not items or len(items) == 0:
        return "No reminders configured."

    reminder_descriptions = []
    for item in items:
        schedule = item.get("schedule", {})
        sched_type = schedule.get("type", "")
        time_of_day = schedule.get("time_of_day", "")

        if sched_type == "recurring":
            unit = schedule.get("unit", "")
            weekdays = schedule.get("weekdays", [])
            month_day = schedule.get("month_day")

            if weekdays:
                days_str = ", ".join(weekdays)
                reminder_descriptions.append(f"Recurring {unit}ly on {days_str} at {time_of_day}")
            elif month_day:
                reminder_descriptions.append(f"Recurring {unit}ly on day {month_day} at {time_of_day}")
            else:
                reminder_descriptions.append(f"Recurring {unit}ly at {time_of_day}")
        elif sched_type == "one_time":
            start_date = schedule.get("start_date", "")
            if start_date and time_of_day:
                reminder_descriptions.append(f"One-time reminder on {start_date} at {time_of_day}")
            elif time_of_day:
                reminder_descriptions.append(f"One-time reminder at {time_of_day}")

    if reminder_descriptions:
        return "Reminders: " + "; ".join(reminder_descriptions)

    return "No reminders configured."
