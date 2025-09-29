from typing import Any

from langgraph.graph import MessagesState


class WealthState(MessagesState):
    tool_call_count: int = 0


def handoff_to_supervisor_node(state: WealthState) -> dict[str, Any]:
    """Node that handles handoff back to supervisor.

    This node determines whether to return control to supervisor or end execution
    based on the execution context.
    """
    from app.agents.supervisor.handoff import create_handoff_back_messages

    analysis_content = ""
    if "messages" in state and isinstance(state["messages"], list):
        for msg in reversed(state["messages"]):
            if (hasattr(msg, "content") and msg.content and
                getattr(msg, "name", None) == "wealth_agent" and
                not getattr(msg, "response_metadata", {}).get("is_handoff_back", False) and
                "Returning control to supervisor" not in str(msg.content)):

                content = msg.content
                if isinstance(content, str) and content.strip():
                    analysis_content = content
                    break

    if not analysis_content.strip():
        analysis_content = "Wealth analysis completed successfully."

    handoff_messages = create_handoff_back_messages("wealth_agent", "supervisor")

    return {
        "messages": [
            {"role": "assistant", "content": analysis_content, "name": "wealth_agent"},
            handoff_messages[0],
        ],
        "tool_call_count": state.tool_call_count if hasattr(state, 'tool_call_count') else state.get('tool_call_count', 0)
    }
