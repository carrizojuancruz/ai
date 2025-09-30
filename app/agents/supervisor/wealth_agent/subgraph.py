from __future__ import annotations

import json
import re
from typing import Callable, List

from langchain_aws import ChatBedrockConverse
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.core.config import config

from .handoff import WealthState, handoff_to_supervisor_node

MAX_TOOL_CALLS = config.WEALTH_AGENT_MAX_TOOL_CALLS


def _parse_used_sources(response, logger) -> List[str]:
    """Parse USED_SOURCES from LLM response content."""
    try:
        content = ""
        if hasattr(response, "content"):
            if isinstance(response.content, str):
                content = response.content
            elif isinstance(response.content, list):
                # Extract text from content blocks
                text_parts = []
                for block in response.content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        text_parts.append(block)
                content = "\n".join(text_parts)
        
        return _parse_used_sources_from_content(content, logger)

    except Exception as e:
        logger.error(f"Failed to parse used sources: {e}")
        return []


def _parse_used_sources_from_content(content: str, logger) -> List[str]:
    """Parse USED_SOURCES from content string."""
    try:
        # Look for USED_SOURCES pattern - handle both formats
        patterns = [
            r'\*\*USED_SOURCES:\*\*\s*\[(.*?)\]',  # **USED_SOURCES:** ["url1", "url2"]
            r'USED_SOURCES:\s*\[(.*?)\]'           # USED_SOURCES: ["url1", "url2"]
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                sources_str = match.group(1).strip()
                if sources_str:
                    # Parse the JSON array of URLs
                    sources_list = json.loads(f'[{sources_str}]')
                    # Filter out non-string values and empty strings
                    used_sources = [url for url in sources_list if isinstance(url, str) and url.strip()]
                    logger.info(f"Parsed {len(used_sources)} used sources from content")
                    return used_sources
                else:
                    logger.info("LLM marked no sources as used (empty USED_SOURCES)")
                    return []

        logger.info("No USED_SOURCES pattern found in content")
        return []

    except Exception as e:
        logger.error(f"Failed to parse used sources from content: {e}")
        return []


def _extract_sources_from_tool_message(messages, logger) -> List[dict]:
    """Extract source metadata from search_kb tool results."""
    extracted_sources = []

    for msg in messages:
        if (hasattr(msg, '__class__') and msg.__class__.__name__ == 'ToolMessage' and
            getattr(msg, 'name', None) == 'search_kb'):
            try:
                content = msg.content
                if isinstance(content, str):
                    # Parse JSON content from search_kb tool
                    search_results = json.loads(content)

                    for result in search_results:
                        if isinstance(result, dict) and 'source' in result:
                            source_entry = {
                                'url': result['source'],
                                'metadata': result.get('metadata', {})
                            }
                            extracted_sources.append(source_entry)

                logger.info(f"Extracted {len(extracted_sources)} sources from search_kb tool message")

            except Exception as e:
                logger.error(f"Failed to extract sources from tool message: {e}")

    return extracted_sources


def _filter_sources_for_response(state: WealthState, logger) -> List[dict]:
    """Filter sources to only include those actually used by the LLM."""
    used_sources = getattr(state, 'used_sources', state.get('used_sources', []))
    retrieved_sources = getattr(state, 'retrieved_sources', state.get('retrieved_sources', []))
    
    if not retrieved_sources:
        logger.info("No retrieved sources to filter")
        return []
        
    if not used_sources:
        logger.info("No used sources marked by LLM, falling back to all retrieved sources")
        return retrieved_sources
        
    # Filter retrieved sources to only include used ones
    filtered = [
        source for source in retrieved_sources
        if source.get("url") in used_sources
    ]
    
    logger.info(f"Filtered to {len(filtered)} used sources from {len(retrieved_sources)} retrieved")
    return filtered


def _clean_response(response, tool_call_count: int, state: dict, logger):
    if hasattr(response, "tool_calls") and response.tool_calls:
        current_calls = len(response.tool_calls)
        total_calls = tool_call_count + current_calls

        if total_calls > MAX_TOOL_CALLS:
            logger.error(f"BLOCKED: Would exceed limit - {current_calls} new calls + {tool_call_count} existing = {total_calls}")
            if tool_call_count > 0:
                return {"role": "assistant", "content": "Based on my knowledge base searches, I have gathered sufficient information to provide a comprehensive response.", "name": "wealth_agent"}
            else:
                limited_tool_calls = response.tool_calls[:MAX_TOOL_CALLS]
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

    async def agent_node(state: WealthState):
        # Handle both WealthState objects and dict states for compatibility
        if hasattr(state, 'tool_call_count'):
            tool_call_count = state.tool_call_count
        else:
            tool_call_count = state.get('tool_call_count', 0)

        if tool_call_count >= MAX_TOOL_CALLS:
            logger.warning(f"Tool call limit reached ({tool_call_count}). Forcing completion.")
            return {"messages": [{"role": "assistant", "content": "Based on my knowledge base searches, I have gathered sufficient information to provide a comprehensive response.", "name": "wealth_agent"}]}

        system_prompt = prompt_builder()
        messages = [{"role": "system", "content": system_prompt}] + state["messages"]

        logger.info(f"Agent processing with {tool_call_count} previous tool calls")
        response = await model_with_tools.ainvoke(messages)

        cleaned_response = _clean_response(response, tool_call_count, state, logger)

        new_tool_call_count = tool_call_count
        if hasattr(cleaned_response, "tool_calls") and cleaned_response.tool_calls:
            new_tool_call_count += len(cleaned_response.tool_calls)

        # Parse used sources from LLM response if it's a final response (no tool calls)
        # Note: We'll do comprehensive parsing in supervisor_node instead
        used_sources = getattr(state, 'used_sources', state.get('used_sources', []))

        # Extract sources from any new tool messages in state
        retrieved_sources = getattr(state, 'retrieved_sources', state.get('retrieved_sources', []))
        new_sources = _extract_sources_from_tool_message(state["messages"], logger)
        if new_sources:
            retrieved_sources.extend(new_sources)
            logger.info(f"Added {len(new_sources)} new sources to retrieved_sources")

        return {
            "messages": [cleaned_response],
            "tool_call_count": new_tool_call_count,
            "retrieved_sources": retrieved_sources,
            "used_sources": used_sources
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

        # Extract used sources and retrieved sources for filtering
        used_sources = getattr(state, 'used_sources', state.get('used_sources', []))
        retrieved_sources = getattr(state, 'retrieved_sources', state.get('retrieved_sources', []))
        
        # Try to parse USED_SOURCES from the final analysis content
        if analysis_content and not used_sources:
            used_sources = _parse_used_sources_from_content(analysis_content, logger)
            logger.info(f"Parsed {len(used_sources)} used sources from final response content")

        # Create a state-like object with updated used_sources for filtering
        filter_state = {
            'used_sources': used_sources,
            'retrieved_sources': retrieved_sources
        }
        
        # Filter retrieved sources to only include used ones
        filtered_sources = _filter_sources_for_response(filter_state, logger)
        
        # Deduplicate filtered sources to show only unique URLs
        unique_filtered_sources = []
        seen_urls = set()
        for source in filtered_sources:
            url = source.get("url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_filtered_sources.append(source)
                logger.info(f"Added unique source: {url}")
            else:
                logger.info(f"Skipped duplicate source: {url}")
        
        logger.info(f"Filtered to {len(unique_filtered_sources)} unique sources from {len(filtered_sources)} total")
        filtered_sources = unique_filtered_sources
        
        formatted_response = f"""===== WEALTH AGENT TASK COMPLETED =====

Task Analyzed: {user_question}

Analysis Results:
{analysis_content}

STATUS: WEALTH AGENT ANALYSIS COMPLETE
This wealth agent analysis is provided to the supervisor for final user response formatting."""

        messages_to_return = [{"role": "assistant", "content": formatted_response, "name": "wealth_agent"}]
        
        return {
            "messages": messages_to_return,
            "tool_call_count": state.tool_call_count if hasattr(state, 'tool_call_count') else state.get('tool_call_count', 0),
            "retrieved_sources": retrieved_sources,
            "used_sources": used_sources,  # Updated used_sources from parsing
            "filtered_sources": filtered_sources,  # Pass deduplicated filtered sources
            "sources": []  # Clear supervisor sources so handoff can replace them
        }

    def should_continue(state: WealthState):
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return "tools"
        return "supervisor"

    workflow = StateGraph(WealthState)
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
