from __future__ import annotations

import json
import operator
import re
from collections import Counter
from typing import Annotated, Any, Callable, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from app.knowledge.internal_sections import InternalSubcategory

USED_SOURCES_PATTERN = re.compile(r'(?:\*\*)?USED_SOURCES:(?:\*\*)?\s*\[(.*?)\]', re.DOTALL)
USED_SUBCATEGORIES_PATTERN = re.compile(r'(?:\*\*)?USED_SUBCATEGORIES:(?:\*\*)?\s*\[(.*?)\]', re.DOTALL)

NAVIGATION_EVENT_MAP: Dict[str, Dict[str, Any]] = {
    InternalSubcategory.REPORTS.value: {
        "event": "navigation.reports",
        "data": {"message": "View your financial reports", "action": "view_reports"},
    },
    InternalSubcategory.PROFILE.value: {
        "event": "navigation.profile",
        "data": {"message": "View your profile", "action": "view_profile"},
    },
    InternalSubcategory.CONNECT_ACCOUNT.value: {
        "event": "navigation.connected-accounts",
        "data": {
            "message": "Connect an account (Financial Info → Connected Accounts) to enable live transaction insights.",
            "action": "connect_accounts",
        },
    },
}


class WealthState(MessagesState):
    retrieved_sources: List[Dict[str, Any]]
    used_sources: List[str]
    filtered_sources: List[Dict[str, Any]]
    navigation_events: List[Dict[str, Any]] | None
    search_count: Annotated[int, operator.add]


def parse_used_sources(content: str) -> List[str]:
    match = USED_SOURCES_PATTERN.search(content)
    if not match:
        return []

    try:
        sources_list = json.loads(f'[{match.group(1).strip()}]')
        return [url for url in sources_list if isinstance(url, str) and url.strip()]
    except (json.JSONDecodeError, ValueError):
        return []


def parse_used_subcategories(content: str) -> List[str]:
    match = USED_SUBCATEGORIES_PATTERN.search(content)
    if not match:
        return []

    try:
        raw_list = json.loads(f'[{match.group(1).strip()}]')
        return [sc for sc in raw_list if isinstance(sc, str) and sc.strip()]
    except (json.JSONDecodeError, ValueError):
        return []


def select_primary_subcategory(subcategories: List[str]) -> Optional[str]:
    if not subcategories:
        return None

    counts = Counter(subcategories)
    max_count = max(counts.values())
    tied = [sc for sc, cnt in counts.items() if cnt == max_count]

    if len(tied) == 1:
        return tied[0]

    for sc in subcategories:
        if sc in tied:
            return sc

    return None


def build_navigation_events(subcategories: List[str]) -> List[Dict[str, Any]]:
    selected = select_primary_subcategory(subcategories)
    if selected and selected in NAVIGATION_EVENT_MAP:
        return [NAVIGATION_EVENT_MAP[selected]]
    return []


def filter_sources_by_urls(sources: List[Dict[str, Any]], urls: List[str]) -> List[Dict[str, Any]]:
    if not sources or not urls:
        return []

    url_set = set(urls)
    seen_urls = set()
    result = []

    for source in sources:
        url = source.get("url")
        if url and url in url_set and url not in seen_urls:
            seen_urls.add(url)
            result.append(source)

    return result


def extract_text_content_from_message(msg) -> str:
    content = msg.content

    if isinstance(content, list):
        text_blocks = [
            block["text"] for block in content
            if isinstance(block, dict) and block.get("type") == "text" and block.get("text")
        ]
        return "\n\n".join(text_blocks) if text_blocks else ""

    if isinstance(content, str):
        return content.strip()

    return ""


def _clean_response(response, state, logger):
    if hasattr(response, "tool_calls") and response.tool_calls:
        return {
            "role": "assistant",
            "content": "",
            "name": "wealth_agent",
            "tool_calls": response.tool_calls
        }

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

            cleaned_content = [
                block for block in response.content
                if not (isinstance(block, dict) and block.get("type") == "reasoning_content")
            ]

            if cleaned_content:
                return {"role": "assistant", "content": cleaned_content, "name": "wealth_agent"}

            return {"role": "assistant", "content": "Based on my knowledge base search, I was unable to find specific information about this topic.", "name": "wealth_agent"}

    return response


def create_wealth_subgraph(
    llm: BaseChatModel,
    tools,
    prompt_builder: Callable[[], str],
    max_tool_calls: int,
):
    import logging
    logger = logging.getLogger(__name__)

    tool_node = ToolNode(tools)
    model_with_tools = llm.bind_tools(tools)

    async def agent_node(state: WealthState):
        current_search_count = state.get("search_count", 0)

        system_prompt = prompt_builder()

        if current_search_count >= max_tool_calls:
            system_prompt += "\n\nIMPORTANT: You have reached the maximum allowed searches. Provide your final answer NOW based on what you found. Do not attempt to call any tools."
            logger.warning(f"[WEALTH_AGENT] Max tool calls ({max_tool_calls}) reached. Removing tools from model.")
            model_to_use = llm
        else:
            model_to_use = model_with_tools

        messages = [{"role": "system", "content": system_prompt}] + state["messages"]

        response = await model_to_use.ainvoke(messages)

        cleaned_response = _clean_response(response, state, logger)

        used_sources = state.get('used_sources', [])
        retrieved_sources = state.get('retrieved_sources', [])

        for msg in state["messages"]:
            if msg.__class__.__name__ == 'ToolMessage' and getattr(msg, 'name', None) == 'search_kb':
                try:
                    search_results = json.loads(msg.content) if isinstance(msg.content, str) else []
                    for result in search_results:
                        if not (isinstance(result, dict) and 'source' in result):
                            continue

                        metadata = result.get('metadata', {})
                        if not isinstance(metadata, dict):
                            metadata = {}

                        source = {
                            'url': result['source'],
                            'name': "Knowledge Base",
                        }

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
                        if metadata.get('subcategory'):
                            source['subcategory'] = metadata['subcategory']

                        retrieved_sources.append(source)
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"[WEALTH_AGENT] Failed to parse search_kb tool message: {e}. Content: {msg.content[:200] if isinstance(msg.content, str) else type(msg.content)}")

        return {
            "messages": [cleaned_response],
            "retrieved_sources": retrieved_sources,
            "used_sources": used_sources,
        }

    def supervisor_node(state: WealthState):
        user_question = next(
            (str(msg.content) for msg in state["messages"]
             if hasattr(msg, "content") and getattr(msg, "type", None) == "human"),
            ""
        )

        analysis_content = ""
        for msg in reversed(state["messages"]):
            if (msg.__class__.__name__ == "AIMessage" and
                hasattr(msg, "content") and msg.content and
                not getattr(msg, "tool_calls", None) and
                not getattr(msg, "response_metadata", {}).get("is_handoff_back", False)):

                text = extract_text_content_from_message(msg)
                if text:
                    analysis_content = text
                    break

        if not analysis_content.strip():
            analysis_content = "The knowledge base search did not return relevant information for this specific question."

        used_sources = state.get('used_sources', [])
        retrieved_sources = state.get('retrieved_sources', [])

        if analysis_content and not used_sources:
            used_sources = parse_used_sources(analysis_content)

        used_sources_filtered = filter_sources_by_urls(retrieved_sources, used_sources)

        used_subcategories = parse_used_subcategories(analysis_content)
        if used_subcategories:
            if used_sources_filtered:
                valid_enum_values = {sc.value for sc in InternalSubcategory}
                valid_subcategories = {
                    source.get('subcategory')
                    for source in used_sources_filtered
                    if source.get('subcategory')
                }
                used_subcategories = [
                    sc for sc in used_subcategories
                    if sc in valid_subcategories and sc in valid_enum_values
                ]
            else:
                used_subcategories = []

        final_sources = [s for s in used_sources_filtered if s.get('content_source') != 'internal']

        search_count = state.get("search_count", 0)
        logger.info(f"[WEALTH_AGENT] Completed with {search_count} search_kb calls")

        formatted_response = f"""===== WEALTH AGENT TASK COMPLETED =====

Task Analyzed: {user_question}

Analysis Results:
{analysis_content}

STATUS: WEALTH AGENT ANALYSIS COMPLETE
This wealth agent analysis is provided to the supervisor for final user response formatting."""

        navigation_events = build_navigation_events(used_subcategories)

        return {
            "messages": [
                {"role": "assistant", "content": formatted_response, "name": "wealth_agent"}
            ],
            "sources": final_sources,
            "navigation_events": navigation_events or None
        }

    async def tools_wrapper_node(state: WealthState):
        """Wrap tool node to increment search count."""
        result = await tool_node.ainvoke(state)

        last_message = state["messages"][-1]
        increment = len(getattr(last_message, "tool_calls", []))

        result["search_count"] = increment

        current_count = state.get("search_count", 0)
        new_count = current_count + increment
        logger.info(f"[WEALTH_AGENT] Tool calls executed: {increment}, Total search count: {new_count}/{max_tool_calls}")

        return result

    def should_continue(state: WealthState):
        """Decide next step: tools or supervisor."""
        last_message = state["messages"][-1]
        current_search_count = state.get("search_count", 0)

        if getattr(last_message, "tool_calls", None):
            if current_search_count >= max_tool_calls:
                logger.info(
                    f"[WEALTH_AGENT] Max tool calls ({max_tool_calls}) reached. "
                    f"Current count: {current_search_count}. Going to supervisor."
                )
                return "supervisor"

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
            "supervisor": "supervisor"
        }
    )
    workflow.add_edge("tools", "agent")

    return workflow.compile()
