from typing import Any
from uuid import UUID

from langgraph.types import Command


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

