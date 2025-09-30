from typing import Any, Dict, List

from langgraph.graph import MessagesState


class WealthState(MessagesState):
    tool_call_count: int = 0
    retrieved_sources: List[Dict[str, Any]] = []
    used_sources: List[str] = []
    filtered_sources: List[Dict[str, Any]] = []


def handoff_to_supervisor_node(state: WealthState) -> dict[str, Any]:
    """Handle handoff back to supervisor with filtered sources."""
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
    filtered_sources = getattr(state, 'filtered_sources', state.get('filtered_sources', []))
    sources_to_use = filtered_sources or getattr(state, 'retrieved_sources', state.get('retrieved_sources', []))

    supervisor_sources = []
    if sources_to_use:
        for source in sources_to_use:
            supervisor_sources.append({
                "name": "Knowledge Base",
                "url": source.get("url", ""),
                **source.get("metadata", {})
            })

    return {
        "messages": [
            {"role": "assistant", "content": analysis_content, "name": "wealth_agent"},
            handoff_messages[0],
        ],
        "sources": supervisor_sources,
        "tool_call_count": getattr(state, 'tool_call_count', 0),
        "retrieved_sources": sources_to_use,
        "used_sources": getattr(state, 'used_sources', state.get('used_sources', [])),
        "filtered_sources": filtered_sources
    }
