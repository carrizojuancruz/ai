from __future__ import annotations

from typing import Any, Sequence

from langchain_aws import ChatBedrockConverse
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode


def _extract_supervisor_text(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                text_value = block.get("text") or block.get("content")
                if isinstance(text_value, str):
                    parts.append(text_value)
        if parts:
            return "\n".join(parts).strip()

    text_attr = getattr(content, "content", None)
    if isinstance(text_attr, str):
        return text_attr

    return str(content) if content else ""


def create_supervisor_subgraph(
    model: ChatBedrockConverse,
    tools: Sequence[Any],
    system_prompt: str,
) -> CompiledStateGraph:
    tool_node = ToolNode(tools)
    model_with_tools = model.bind_tools(tools)

    async def agent_node(state: MessagesState):
        messages = [{"role": "system", "content": system_prompt}] + (state.get("messages") or [])
        response = await model_with_tools.ainvoke(messages)
        return {"messages": [response]}

    def supervisor_node(state: MessagesState):
        analysis_content = ""
        for message in reversed(state.get("messages") or []):
            role = getattr(message, "role", None)
            if role is None and isinstance(message, dict):
                role = message.get("role")

            msg_type = getattr(message, "type", None)
            if msg_type is None and isinstance(message, dict):
                msg_type = message.get("type")

            content = getattr(message, "content", None)
            if content is None and isinstance(message, dict):
                content = message.get("content")

            if (role == "assistant" or msg_type == "ai") and content:
                analysis_content = _extract_supervisor_text(content)
                if analysis_content:
                    break

        if not analysis_content:
            return {}

        last_entry = (state.get("messages") or [])[-1]
        name = getattr(last_entry, "name", None)
        if name is None and isinstance(last_entry, dict):
            name = last_entry.get("name")

        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": analysis_content,
                    "name": name or "supervisor",
                }
            ]
        }

    def should_continue(state: MessagesState):
        messages = state.get("messages") or []
        if not messages:
            return "supervisor"

        last_message = messages[-1]
        tool_calls = getattr(last_message, "tool_calls", None)
        if tool_calls:
            return "tools"
        if isinstance(last_message, dict) and last_message.get("tool_calls"):
            return "tools"
        return "supervisor"

    workflow = StateGraph(MessagesState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    workflow.add_node("supervisor", supervisor_node)

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue)
    workflow.add_edge("tools", "agent")

    return workflow.compile()
