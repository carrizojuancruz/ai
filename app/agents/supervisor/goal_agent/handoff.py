from typing import Any

from langgraph.graph import MessagesState


def handoff_to_supervisor_node(state: MessagesState) -> dict[str, Any]:
    """Node that handles handoff back to supervisor.

    This node determines whether to return control to supervisor or end execution
    based on the execution context.
    """
    from app.agents.supervisor.handoff import create_handoff_back_messages

    # Extract the last assistant message to include in handoff
    last_message = ""
    if "messages" in state and isinstance(state["messages"], list):
        for msg in reversed(state["messages"]):
            if hasattr(msg, "content") and getattr(msg, "name", None) == "goal_agent":
                last_message = str(msg.content)
                break

    if not last_message.strip():
        last_message = "Goal agent task completed successfully."

    # Create handoff messages to return control to supervisor
    handoff_messages = create_handoff_back_messages("goal_agent", "supervisor")

    # Return the result with handoff messages
    return {
        "messages": [
            {"role": "assistant", "content": last_message, "name": "goal_agent"},
            handoff_messages[0],
        ]
    }
