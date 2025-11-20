from __future__ import annotations

import json
import operator
import re
from typing import Annotated, Any, Callable, Dict, List

from langchain_core.language_models import BaseChatModel
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from app.core.config import config

MAX_TOOL_CALLS: int = config.WEALTH_AGENT_MAX_TOOL_CALLS
RECURSION_LIMIT: int = 15
DEFAULT_TEMPERATURE: float = 0.4

class WealthState(MessagesState):
    retrieved_sources: List[Dict[str, Any]]
    used_sources: List[str]
    filtered_sources: List[Dict[str, Any]]
    navigation_events: List[Dict[str, Any]] | None
    search_count: Annotated[int, operator.add]


def _clean_response(response, state, logger):
    if hasattr(response, "tool_calls") and response.tool_calls:
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
                return {"role": "assistant", "content": "I need to search my knowledge base to provide accurate information about this topic.", "name": "wealth_agent"}
            else:
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
    llm: BaseChatModel,
    tools,
    prompt_builder: Callable[[], str],
):
    import logging
    logger = logging.getLogger(__name__)

    tool_node = ToolNode(tools)
    model_with_tools = llm.bind_tools(tools)

    async def agent_node(state: WealthState):
        current_search_count = state.get("search_count", 0)

        system_prompt = prompt_builder()

        if current_search_count >= MAX_TOOL_CALLS:
            system_prompt += "\n\nWARNING: You have reached the maximum allowed searches. Do NOT call search_kb again. Provide your final answer now based on what you found, or state that you could not find the information in the knowledge base."

        messages = [{"role": "system", "content": system_prompt}] + state["messages"]

        response = await model_with_tools.ainvoke(messages)

        cleaned_response = _clean_response(response, state, logger)


        used_sources = getattr(state, 'used_sources', state.get('used_sources', []))

        retrieved_sources = getattr(state, 'retrieved_sources', state.get('retrieved_sources', []))
        navigation_events = getattr(state, 'navigation_events', state.get('navigation_events')) or []
        seen_navigation_events = {event.get("event") for event in navigation_events if isinstance(event, dict)}

        for msg in state["messages"]:
            if getattr(getattr(msg, '__class__', None), '__name__', None) == 'ToolMessage' and getattr(msg, 'name', None) == 'search_kb':
                try:
                    if isinstance(msg.content, str):
                        search_results = json.loads(msg.content)
                        new_sources = []
                        for result in search_results:
                            if isinstance(result, dict) and 'source' in result:
                                source = {'url': result['source']}
                                metadata = result.get('metadata', {})

                                source['name'] = "Knowledge Base"

                                if isinstance(metadata, dict):
                                    if metadata.get('name'):
                                        source['source_name'] = metadata['name']
                                    if metadata.get('type'):
                                        source['type'] = metadata['type']
                                    if metadata.get('category'):
                                        source['category'] = metadata['category']
                                    if metadata.get('description'):
                                        source['description'] = metadata['description']
                                    if metadata.get('content_source'):
                                        source['content_source'] = metadata['content_source']

                                    subcategory = metadata.get('subcategory')
                                    if subcategory == 'reports' and "navigation.reports" not in seen_navigation_events:
                                        navigation_events.append({
                                            "event": "navigation.reports",
                                            "data": {
                                                "message": "View your financial reports",
                                                "action": "view_reports",
                                            },
                                        })
                                        seen_navigation_events.add("navigation.reports")

                                    if subcategory == 'profile' and "navigation.profile" not in seen_navigation_events:
                                        navigation_events.append({
                                            "event": "navigation.profile",
                                            "data": {
                                                "message": "View your profile",
                                                "action": "view_profile",
                                            },
                                        })
                                        seen_navigation_events.add("navigation.profile")

                                    if subcategory == 'connect-account' and "navigation.connected-accounts" not in seen_navigation_events:
                                        navigation_events.append({
                                            "event": "navigation.connected-accounts",
                                            "data": {
                                                "message": "Connect an account (Financial Info → Connected Accounts) to enable live transaction insights.",
                                                "action": "connect_accounts",
                                            },
                                        })
                                        seen_navigation_events.add("navigation.connected-accounts")

                                new_sources.append(source)
                        retrieved_sources.extend(new_sources)
                except Exception:
                    pass

        return {
            "messages": [cleaned_response],
            "retrieved_sources": retrieved_sources,
            "used_sources": used_sources,
            "navigation_events": navigation_events if navigation_events else None
        }

    def supervisor_node(state: WealthState):
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

        used_sources = getattr(state, 'used_sources', state.get('used_sources', []))
        retrieved_sources = getattr(state, 'retrieved_sources', state.get('retrieved_sources', []))

        if analysis_content and not used_sources:
            try:
                match = re.search(r'(?:\*\*)?USED_SOURCES:(?:\*\*)?\s*\[(.*?)\]', analysis_content, re.DOTALL)
                if match and match.group(1).strip():
                    sources_list = json.loads(f'[{match.group(1).strip()}]')
                    used_sources = [url for url in sources_list if isinstance(url, str) and url.strip()]
            except Exception:
                pass

        filtered_sources = []
        if retrieved_sources and used_sources:
            filtered_sources = [source for source in retrieved_sources if source.get("url") in used_sources]

        unique_filtered_sources = []
        seen_urls = set()
        for source in filtered_sources:
            url = source.get("url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_filtered_sources.append(source)

        final_sources = [s for s in unique_filtered_sources if s.get('content_source') != 'internal']

        search_count = state.get("search_count", 0)
        logger.info(f"[WEALTH_AGENT] Completed with {search_count} search_kb calls")

        formatted_response = f"""===== WEALTH AGENT TASK COMPLETED =====

Task Analyzed: {user_question}

Analysis Results:
{analysis_content}

STATUS: WEALTH AGENT ANALYSIS COMPLETE
This wealth agent analysis is provided to the supervisor for final user response formatting."""

        navigation_events = getattr(state, 'navigation_events', state.get('navigation_events')) or []

        return {
            "messages": [
                {"role": "assistant", "content": formatted_response, "name": "wealth_agent"}
            ],
            "sources": final_sources,
            "navigation_events": navigation_events if navigation_events else None
        }

    async def tools_wrapper_node(state: WealthState):
        """Wrap tool node to increment search count."""
        result = await tool_node.ainvoke(state)

        result["search_count"] = 1

        current_count = state.get("search_count", 0)
        logger.info(f"[WEALTH_AGENT] Search count: {current_count + 1}/{MAX_TOOL_CALLS}")

        return result

    def should_continue(state: WealthState):
        """Decide next step: tools, supervisor, or stop."""
        last_message = state["messages"][-1]

        if getattr(last_message, "tool_calls", None):
            current_search_count = state.get("search_count", 0)

            if current_search_count >= MAX_TOOL_CALLS:
                logger.warning(
                    f"[WEALTH_AGENT] Max searches ({MAX_TOOL_CALLS}) reached. "
                    f"Preventing further tool calls. Agent must respond now."
                )
                return "agent_forced_response"

            return "tools"

        return "supervisor"

    workflow = StateGraph(WealthState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tools_wrapper_node)
    workflow.add_node("supervisor", supervisor_node)

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "agent_forced_response": "supervisor",
            "supervisor": "supervisor"
        }
    )
    workflow.add_edge("tools", "agent")

    return workflow.compile()
