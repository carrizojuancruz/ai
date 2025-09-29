from __future__ import annotations

from typing import Awaitable, Callable

from langchain_aws import ChatBedrockConverse
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from app.agents.supervisor.handoff import create_handoff_back_messages


def create_finance_subgraph(
    sql_generator: ChatBedrockConverse,
    tools,
    prompt_builder: Callable[[], Awaitable[str]],
):
    tool_node = ToolNode(tools)
    model_with_tools = sql_generator.bind_tools(tools)

    async def agent_node(state: MessagesState):
        system_prompt = await prompt_builder()
        messages = [{"role": "system", "content": system_prompt}] + state["messages"]
        response = await model_with_tools.ainvoke(messages)
        return {"messages": [response]}

    def supervisor_node(state: MessagesState):
        analysis_content = ""
        for msg in reversed(state["messages"]):
            if (hasattr(msg, "role") and msg.role == "assistant" and hasattr(msg, "content") and msg.content):
                if isinstance(msg.content, list):
                    for content_block in msg.content:
                        if isinstance(content_block, dict) and content_block.get("type") == "text":
                            analysis_content = content_block.get("text", "")
                            break
                else:
                    analysis_content = msg.content
                break

        analysis_response = f"""
        FINANCIAL ANALYSIS COMPLETE:

        Analysis Results:
        {analysis_content}

        This analysis is provided to the supervisor for final user response formatting.
        """

        handoff_messages = create_handoff_back_messages("finance_agent", "supervisor")
        return {
            "messages": [
                {"role": "assistant", "content": analysis_response, "name": "finance_agent"},
                handoff_messages[0],
            ]
        }

    def should_continue(state: MessagesState):
        last_message = state["messages"][-1]
        if last_message.tool_calls:
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


