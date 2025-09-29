from __future__ import annotations

from typing import Callable

from langchain_aws import ChatBedrockConverse
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from .handoff import handoff_to_supervisor_node


def _clean_response(response, tool_call_count: int, state: dict, logger):
    if hasattr(response, "tool_calls") and response.tool_calls:
        current_calls = len(response.tool_calls)
        total_calls = tool_call_count + current_calls

        if total_calls > 5:
            logger.error(f"BLOCKED: Would exceed limit - {current_calls} new calls + {tool_call_count} existing = {total_calls}")
            if tool_call_count > 0:
                return {"role": "assistant", "content": "Based on my knowledge base searches, I have gathered sufficient information to provide a comprehensive response.", "name": "wealth_agent"}
            else:
                limited_tool_calls = response.tool_calls[:5]
                clean_response = {
                    "role": "assistant",
                    "content": "",
                    "name": "wealth_agent",
                    "tool_calls": limited_tool_calls
                }
                logger.warning(f"Truncated tool calls from {current_calls} to {len(limited_tool_calls)}")
                return clean_response

        logger.warning("BLOCKED: Agent attempting to provide content while making tool calls - this is hallucination")

        clean_response = {
            "role": "assistant",
            "content": "",
            "name": "wealth_agent",
            "tool_calls": response.tool_calls
        }
        return clean_response

    if hasattr(response, "content") and isinstance(response.content, list):
        has_reasoning = any(
            isinstance(block, dict) and block.get("type") == "reasoning_content"
            for block in response.content
        )
        if has_reasoning:
            has_tool_results = any(
                msg.__class__.__name__ == "ToolMessage"
                for msg in state.get("messages", [])
            )

            if not has_tool_results:
                logger.error("BLOCKED: Response with reasoning content but no tool results - agent should search first")
                return {"role": "assistant", "content": "I need to search my knowledge base to provide accurate information about this topic.", "name": "wealth_agent"}
            else:
                logger.info("Cleaning reasoning content from final response after tool usage")
                cleaned_content = []
                for block in response.content:
                    if isinstance(block, dict) and block.get("type") == "reasoning_content":
                        continue
                    else:
                        cleaned_content.append(block)

                if cleaned_content:
                    return {"role": "assistant", "content": cleaned_content, "name": "wealth_agent"}
                else:
                    return {"role": "assistant", "content": "Based on my knowledge base search, I was unable to find specific information about this topic.", "name": "wealth_agent"}

    return response

def create_wealth_subgraph(
    llm: ChatBedrockConverse,
    tools,
    prompt_builder: Callable[[], str],
):
    import logging
    logger = logging.getLogger(__name__)

    tool_node = ToolNode(tools)
    model_with_tools = llm.bind_tools(tools)

    async def agent_node(state: MessagesState):
        tool_call_count = 0
        for msg in state["messages"]:
            if (hasattr(msg, "tool_calls") and msg.tool_calls and
                getattr(msg, "role", None) == "assistant"):
                tool_call_count += len(msg.tool_calls)

        if tool_call_count >= 5:
            logger.warning(f"Tool call limit reached ({tool_call_count}). Forcing completion.")
            return {"messages": [{"role": "assistant", "content": "Based on my knowledge base searches, I have gathered sufficient information to provide a comprehensive response.", "name": "wealth_agent"}]}

        system_prompt = prompt_builder()
        messages = [{"role": "system", "content": system_prompt}] + state["messages"]

        logger.info(f"Agent processing with {tool_call_count} previous tool calls")
        response = await model_with_tools.ainvoke(messages)

        cleaned_response = _clean_response(response, tool_call_count, state, logger)
        return {"messages": [cleaned_response]}

    def supervisor_node(state: MessagesState):
        analysis_content = ""
        user_question = ""

        for msg in state["messages"]:
            if hasattr(msg, "content") and getattr(msg, "type", None) == "human":
                user_question = str(msg.content)
                break

        for msg in reversed(state["messages"]):
            if (msg.__class__.__name__ == "AIMessage" and
                hasattr(msg, "content") and msg.content and
                not getattr(msg, "tool_calls", None) and
                not getattr(msg, "response_metadata", {}).get("is_handoff_back", False)):

                content = msg.content

                if isinstance(content, list):
                    text_blocks = []
                    for content_block in content:
                        if (isinstance(content_block, dict) and
                            content_block.get("type") == "text" and
                            content_block.get("text")):
                            text_blocks.append(content_block["text"])

                    if text_blocks:
                        analysis_content = "\n\n".join(text_blocks)
                        break
                elif isinstance(content, str) and content.strip():
                    analysis_content = content
                    break

        if not analysis_content.strip():
            analysis_content = "The knowledge base search did not return relevant information for this specific question."

        formatted_response = f"""===== WEALTH AGENT TASK COMPLETED =====

Task Analyzed: {user_question}

Analysis Results:
{analysis_content}

STATUS: WEALTH AGENT ANALYSIS COMPLETE
This wealth agent analysis is provided to the supervisor for final user response formatting."""

        return {
            "messages": [
                {"role": "assistant", "content": formatted_response, "name": "wealth_agent"}
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

    workflow.add_node("handoff_to_supervisor", handoff_to_supervisor_node)

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue)
    workflow.add_edge("tools", "agent")
    workflow.add_edge("supervisor", "handoff_to_supervisor")
    workflow.add_edge("handoff_to_supervisor", END)

    return workflow.compile(checkpointer=None)
