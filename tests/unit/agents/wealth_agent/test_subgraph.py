"""Core integration tests for wealth agent subgraph.

Helper function tests are in:
- test_helper_functions.py (filter_sources_by_urls, extract_text_content_from_message, select_primary_subcategory)
- test_parsing_functions.py (parse_used_sources, parse_used_subcategories)
"""

import logging
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import HumanMessage, ToolMessage

from app.agents.supervisor.wealth_agent.subgraph import (
    WealthState,
    _clean_response,
    create_wealth_subgraph,
)


@pytest.mark.unit
class TestWealthState:
    """Test suite for WealthState class."""

    def test_wealth_state_with_messages(self):
        """Test WealthState stores messages correctly."""
        messages = [HumanMessage(content="Test")]
        state = WealthState(messages=messages)

        assert len(state["messages"]) == 1
        assert state["messages"][0].content == "Test"

    def test_wealth_state_dict_access(self):
        """Test WealthState supports dict access."""
        state = WealthState(
            messages=[],
            retrieved_sources=[{"url": "test.com"}],
        )

        assert len(state["retrieved_sources"]) == 1

    def test_wealth_state_default_values(self):
        """Test WealthState initializes with defaults."""
        state = WealthState(messages=[])

        assert state.get("retrieved_sources", []) == []
        assert state.get("used_sources", []) == []
        assert state.get("filtered_sources", []) == []


@pytest.mark.unit
class TestCleanResponse:
    """Test suite for _clean_response function."""

    def test_clean_response_with_tool_calls_removes_content(self):
        """Test _clean_response removes content when tool calls present."""
        logger = logging.getLogger(__name__)
        mock_response = MagicMock()
        mock_response.tool_calls = [{"name": "search_kb"}]
        mock_response.content = "This should be removed"

        result = _clean_response(mock_response, {}, logger)

        assert result["content"] == ""
        assert result["tool_calls"] == mock_response.tool_calls

    def test_clean_response_with_reasoning_content_no_tools(self):
        """Test _clean_response blocks reasoning without tool results."""
        logger = logging.getLogger(__name__)
        mock_response = MagicMock()
        mock_response.tool_calls = []
        mock_response.content = [
            {"type": "reasoning_content", "text": "Thinking..."},
            {"type": "text", "text": "Answer"},
        ]

        state = {"messages": [HumanMessage(content="Question")]}

        result = _clean_response(mock_response, state, logger)

        assert isinstance(result, dict)
        assert "search" in result["content"].lower()

    def test_clean_response_cleans_reasoning_after_tool_usage(self):
        """Test _clean_response removes reasoning after tool usage."""
        logger = logging.getLogger(__name__)
        mock_response = MagicMock()
        mock_response.tool_calls = []
        mock_response.content = [
            {"type": "reasoning_content", "text": "Thinking..."},
            {"type": "text", "text": "Final answer"},
        ]

        state = {
            "messages": [
                HumanMessage(content="Question"),
                ToolMessage(content="Result", tool_call_id="123"),
            ]
        }

        result = _clean_response(mock_response, state, logger)

        assert isinstance(result, dict)
        assert isinstance(result.get("content"), list)
        assert any(isinstance(block, dict) and block.get("type") == "text" for block in result["content"])

    def test_clean_response_empty_after_reasoning_removal(self):
        """Test _clean_response handles empty content after removing reasoning."""
        logger = logging.getLogger(__name__)
        mock_response = MagicMock()
        mock_response.tool_calls = []
        mock_response.content = [
            {"type": "reasoning_content", "text": "Only reasoning"},
        ]

        state = {"messages": [ToolMessage(content="Result", tool_call_id="123")]}

        result = _clean_response(mock_response, state, logger)

        assert isinstance(result, dict)
        assert isinstance(result.get("content"), str)
        assert "unable to find" in result["content"].lower()

    def test_clean_response_returns_unchanged_when_no_issues(self):
        """Test _clean_response returns response unchanged when valid."""
        logger = logging.getLogger(__name__)
        mock_response = MagicMock()
        mock_response.tool_calls = []
        mock_response.content = "Valid final response"

        result = _clean_response(mock_response, {}, logger)

        assert result == mock_response


@pytest.mark.unit
class TestCreateWealthSubgraph:
    """Test suite for create_wealth_subgraph function."""

    def test_create_wealth_subgraph_returns_graph(self):
        """Test create_wealth_subgraph creates a graph."""
        mock_llm = MagicMock()

        def prompt_builder():
            return "System prompt"

        graph = create_wealth_subgraph(mock_llm, [], prompt_builder, max_tool_calls=1)

        assert graph is not None
        assert hasattr(graph, "ainvoke")

    def test_create_wealth_subgraph_accepts_llm(self):
        """Test create_wealth_subgraph accepts an LLM parameter."""
        mock_llm = MagicMock()

        def prompt_builder():
            return "Test"

        graph = create_wealth_subgraph(mock_llm, [], prompt_builder, max_tool_calls=1)

        assert graph is not None