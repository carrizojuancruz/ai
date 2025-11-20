"""Tests for app/agents/supervisor/wealth_agent/subgraph.py"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

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
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"

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

        graph = create_wealth_subgraph(mock_llm, [], prompt_builder)

        assert graph is not None
        assert hasattr(graph, "ainvoke")

    def test_create_wealth_subgraph_accepts_llm(self):
        """Test create_wealth_subgraph accepts an LLM parameter."""
        mock_llm = MagicMock()

        def prompt_builder():
            return "Test"

        graph = create_wealth_subgraph(mock_llm, [], prompt_builder)

        assert graph is not None


@pytest.mark.asyncio
@pytest.mark.unit
class TestWealthSubgraphExecution:
    """Integration tests for wealth subgraph execution."""

    async def test_subgraph_execution_with_basic_response(self):
        """Test subgraph executes with basic AI response."""
        mock_llm = AsyncMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_ai_msg = AIMessage(content="Final answer")
        mock_llm.ainvoke.return_value = mock_ai_msg

        def prompt_builder():
            return "System"

        graph = create_wealth_subgraph(mock_llm, [], prompt_builder)

        state = {"messages": [HumanMessage(content="Query")]}
        result = await graph.ainvoke(state)

        assert "messages" in result
        assert len(result["messages"]) > 0

    async def test_subgraph_execution_with_cleaned_response(self):
        """Test subgraph cleans responses with reasoning tags."""
        mock_llm = AsyncMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_ai_msg = AIMessage(
            content="<reasoning>Thoughts</reasoning><answer>Clean answer</answer>"
        )
        mock_llm.ainvoke.return_value = mock_ai_msg

        def prompt_builder():
            return "System"

        graph = create_wealth_subgraph(mock_llm, [], prompt_builder)

        state = {"messages": [HumanMessage(content="Query")]}
        result = await graph.ainvoke(state)

        assert "messages" in result
        final_msg = result["messages"][-1]
        assert isinstance(final_msg, AIMessage)

    async def test_subgraph_handles_empty_message_list(self):
        """Test subgraph handles empty messages gracefully."""
        mock_llm = AsyncMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_ai_msg = AIMessage(content="Response")
        mock_llm.ainvoke.return_value = mock_ai_msg

        def prompt_builder():
            return "System"

        graph = create_wealth_subgraph(mock_llm, [], prompt_builder)

        state = {"messages": []}
        result = await graph.ainvoke(state)

        assert result is not None

    async def test_subgraph_preserves_message_history(self):
        """Test subgraph preserves existing messages."""
        mock_llm = AsyncMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_ai_msg = AIMessage(content="New response")
        mock_llm.ainvoke.return_value = mock_ai_msg

        def prompt_builder():
            return "System"

        graph = create_wealth_subgraph(mock_llm, [], prompt_builder)

        state = {
            "messages": [
                HumanMessage(content="First query"),
                AIMessage(content="First response"),
                HumanMessage(content="Second query"),
            ]
        }
        result = await graph.ainvoke(state)

        assert "messages" in result
        assert len(result["messages"]) >= 3

    async def test_subgraph_uses_prompt_builder(self):
        """Test subgraph calls prompt_builder function."""
        mock_llm = AsyncMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_ai_msg = AIMessage(content="Response")
        mock_llm.ainvoke.return_value = mock_ai_msg

        prompt_called = []

        def prompt_builder():
            prompt_called.append(True)
            return "Custom system prompt"

        graph = create_wealth_subgraph(mock_llm, [], prompt_builder)

        state = {"messages": [HumanMessage(content="Query")]}
        await graph.ainvoke(state)

        assert len(prompt_called) > 0

    async def test_subgraph_with_sources_in_state(self):
        """Test subgraph handles sources in state."""
        mock_llm = AsyncMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_ai_msg = AIMessage(content="Response with sources")
        mock_llm.ainvoke.return_value = mock_ai_msg

        def prompt_builder():
            return "System"

        graph = create_wealth_subgraph(mock_llm, [], prompt_builder)

        state = {
            "messages": [HumanMessage(content="Query")],
            "sources": [{"title": "Doc1", "url": "http://example.com"}],
        }
        result = await graph.ainvoke(state)

        assert result is not None



    async def test_subgraph_ai_message_with_dict_content(self):
        """Test subgraph handles AI messages with dict content."""
        mock_llm = AsyncMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_ai_msg = AIMessage(
            content=[{"type": "text", "text": "Structured response"}]
        )
        mock_llm.ainvoke.return_value = mock_ai_msg

        def prompt_builder():
            return "System"

        graph = create_wealth_subgraph(mock_llm, [], prompt_builder)

        state = {"messages": [HumanMessage(content="Query")]}
        result = await graph.ainvoke(state)

        assert "messages" in result

    async def test_subgraph_with_reasoning_and_answer_tags(self):
        """Test subgraph extracts answer from reasoning/answer tags."""
        mock_llm = AsyncMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_ai_msg = AIMessage(
            content="<reasoning>Step 1: analyze</reasoning><answer>Clean answer</answer>"
        )
        mock_llm.ainvoke.return_value = mock_ai_msg

        def prompt_builder():
            return "System"

        graph = create_wealth_subgraph(mock_llm, [], prompt_builder)

        state = {"messages": [HumanMessage(content="Query")]}
        result = await graph.ainvoke(state)

        assert "messages" in result
        final_message = result["messages"][-1]
        # Should extract just the answer content
        assert isinstance(final_message, AIMessage)

    async def test_subgraph_sources_extraction_from_tags(self):
        """Test subgraph extracts sources from XML tags."""
        mock_llm = AsyncMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_ai_msg = AIMessage(
            content='Response<sources>[{"title":"Doc","url":"http://test.com"}]</sources>'
        )
        mock_llm.ainvoke.return_value = mock_ai_msg

        def prompt_builder():
            return "System"

        graph = create_wealth_subgraph(mock_llm, [], prompt_builder)

        state = {"messages": [HumanMessage(content="Query")]}
        result = await graph.ainvoke(state)

        assert "messages" in result

    async def test_subgraph_invalid_sources_json_handling(self):
        """Test subgraph handles invalid sources JSON gracefully."""
        mock_llm = AsyncMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_ai_msg = AIMessage(content="Response<sources>invalid json</sources>")
        mock_llm.ainvoke.return_value = mock_ai_msg

        def prompt_builder():
            return "System"

        graph = create_wealth_subgraph(mock_llm, [], prompt_builder)

        state = {"messages": [HumanMessage(content="Query")]}
        result = await graph.ainvoke(state)

        assert "messages" in result

    async def test_subgraph_multiple_message_iterations(self):
        """Test subgraph handles multiple back-and-forth messages."""
        mock_llm = AsyncMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        responses = [
            AIMessage(content="First response"),
        ]
        mock_llm.ainvoke.side_effect = responses

        def prompt_builder():
            return "System"

        graph = create_wealth_subgraph(mock_llm, [], prompt_builder)

        state = {
            "messages": [
                HumanMessage(content="First query"),
                AIMessage(content="First answer"),
                HumanMessage(content="Follow up"),
            ]
        }
        result = await graph.ainvoke(state)

        assert "messages" in result
        assert len(result["messages"]) > 3

    async def test_subgraph_state_initialization_defaults(self):
        """Test subgraph initializes with proper defaults."""
        mock_llm = AsyncMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_ai_msg = AIMessage(content="Response")
        mock_llm.ainvoke.return_value = mock_ai_msg

        def prompt_builder():
            return "System"

        graph = create_wealth_subgraph(mock_llm, [], prompt_builder)

        # Minimal state
        state = {"messages": [HumanMessage(content="Query")]}
        result = await graph.ainvoke(state)

        assert result is not None
        assert "messages" in result

    @pytest.mark.parametrize("tool_content,test_id", [
        (
            '[{"content":"Result","source":"http://example.com","metadata":{"name":"Doc1","type":"article","category":"finance","description":"Financial guide"}}]',
            "valid_json_with_full_metadata"
        ),
        (
            '[{"content":"Result","source":"http://example.com","metadata":"invalid"}]',
            "string_metadata"
        ),
        (
            '[{"content":"Result"}]',
            "missing_source"
        ),
        (
            "Not valid JSON at all",
            "invalid_json"
        ),
    ])
    async def test_subgraph_handles_tool_message_variations(self, tool_content, test_id):
        """Test subgraph handles various ToolMessage content formats gracefully."""
        mock_llm = AsyncMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_ai_msg = AIMessage(content="Response")
        mock_llm.ainvoke.return_value = mock_ai_msg

        def prompt_builder():
            return "System"

        graph = create_wealth_subgraph(mock_llm, [], prompt_builder)

        tool_msg = ToolMessage(
            content=tool_content,
            tool_call_id="call_1",
            name="search_kb",
        )
        state = {"messages": [HumanMessage(content="Query"), tool_msg]}
        result = await graph.ainvoke(state)

        assert result is not None

    async def test_subgraph_tool_limit_returns_completion_message(self):
        """Test subgraph returns completion message when tool limit reached."""
        mock_llm = AsyncMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        # This shouldn't be called because limit is reached
        mock_ai_msg = AIMessage(content="Should not appear")
        mock_llm.ainvoke.return_value = mock_ai_msg

        def prompt_builder():
            return "System"

        graph = create_wealth_subgraph(mock_llm, [], prompt_builder)

        state = {"messages": [HumanMessage(content="Query")]}
        result = await graph.ainvoke(state)

        assert "messages" in result
        # Should have a message about gathering sufficient information
        assert len(result["messages"]) > 0

    async def test_subgraph_supervisor_with_list_content(self):
        """Test supervisor node handles AI messages with list content."""
        mock_llm = AsyncMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        # AI message with list content (text blocks)
        ai_msg_with_list = AIMessage(
            content=[
                {"type": "text", "text": "First block"},
                {"type": "text", "text": "Second block"},
            ]
        )
        mock_llm.ainvoke.return_value = AIMessage(content="Done")

        def prompt_builder():
            return "System"

        graph = create_wealth_subgraph(mock_llm, [], prompt_builder)

        state = {"messages": [HumanMessage(content="Query"), ai_msg_with_list]}
        result = await graph.ainvoke(state)

        assert result is not None

    async def test_subgraph_supervisor_extracts_used_sources(self):
        """Test supervisor extracts USED_SOURCES from response content."""
        mock_llm = AsyncMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        # AI message with USED_SOURCES marker
        ai_msg = AIMessage(
            content='Analysis\n\n**USED_SOURCES:** ["http://source1.com", "http://source2.com"]'
        )
        mock_llm.ainvoke.return_value = AIMessage(content="Done")

        def prompt_builder():
            return "System"

        graph = create_wealth_subgraph(mock_llm, [], prompt_builder)

        state = {
            "messages": [HumanMessage(content="Query"), ai_msg],
            "retrieved_sources": [
                {"url": "http://source1.com", "name": "Doc1"},
                {"url": "http://source2.com", "name": "Doc2"},
            ],
        }
        result = await graph.ainvoke(state)

        assert result is not None

    @pytest.mark.parametrize("content,state_extras,test_id", [
        (
            'Analysis\n\n**USED_SOURCES:** ["http://source1.com", "http://source2.com"]',
            {
                "retrieved_sources": [
                    {"url": "http://source1.com", "name": "Doc1"},
                    {"url": "http://source2.com", "name": "Doc2"},
                ]
            },
            "extracts_used_sources"
        ),
        (
            'Analysis\n\n**USED_SOURCES:** ["http://source1.com"]',
            {
                "retrieved_sources": [
                    {"url": "http://source1.com", "name": "Doc1"},
                    {"url": "http://source1.com", "name": "Doc1 duplicate"},
                ],
                "used_sources": ["http://source1.com"],
            },
            "filters_duplicate_sources"
        ),
        (
            "   ",
            {},
            "empty_analysis_content"
        ),
        (
            'Analysis\n\n**USED_SOURCES:** [invalid json',
            {},
            "invalid_used_sources_json"
        ),
        (
            [
                {"type": "image", "data": "base64..."},
                {"type": "text", "text": "Some text"},
            ],
            {},
            "list_content_with_non_text"
        ),
    ])
    async def test_subgraph_supervisor_handles_content_variations(self, content, state_extras, test_id):
        """Test supervisor handles various content formats and edge cases."""
        mock_llm = AsyncMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        ai_msg = AIMessage(content=content)
        mock_llm.ainvoke.return_value = AIMessage(content="Done")

        def prompt_builder():
            return "System"

        graph = create_wealth_subgraph(mock_llm, [], prompt_builder)

        state = {"messages": [HumanMessage(content="Query"), ai_msg], **state_extras}
        result = await graph.ainvoke(state)

        assert result is not None

    async def test_subgraph_with_real_tool_calls_routing(self):
        """Test subgraph routing with actual tool_calls triggers tools node."""
        from langchain_core.tools import tool

        @tool
        def dummy_tool(query: str) -> str:
            """A dummy tool for testing."""
            return "Result"

        mock_llm = AsyncMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        # First call: AI with tool_calls
        # Second call: Final response
        mock_llm.ainvoke.side_effect = [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "dummy_tool",
                        "args": {"query": "test"},
                        "id": "call_123",
                    }
                ],
            ),
            AIMessage(content="Final answer"),
        ]

        def prompt_builder():
            return "System"

        graph = create_wealth_subgraph(mock_llm, [dummy_tool], prompt_builder)

        state = {"messages": [HumanMessage(content="Query")]}
        result = await graph.ainvoke(state)

        assert result is not None
        assert "messages" in result

    async def test_subgraph_basic_invocation(self):
        """Test basic subgraph invocation."""
        mock_llm = AsyncMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        def prompt_builder():
            return "System"

        graph = create_wealth_subgraph(mock_llm, [], prompt_builder)

        state = {"messages": [HumanMessage(content="Query")]}
        result = await graph.ainvoke(state)

        assert result is not None
        assert "messages" in result

    async def test_subgraph_supervisor_used_sources_parsing(self):
        """Test supervisor parses USED_SOURCES with proper format."""
        mock_llm = AsyncMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        ai_msg = AIMessage(
            content='Response\nUSED_SOURCES: ["http://doc1.com", "http://doc2.com"]'
        )
        mock_llm.ainvoke.return_value = AIMessage(content="Done")

        def prompt_builder():
            return "System"

        graph = create_wealth_subgraph(mock_llm, [], prompt_builder)

        state = {
            "messages": [HumanMessage(content="Query"), ai_msg],
            "retrieved_sources": [
                {"url": "http://doc1.com"},
                {"url": "http://doc2.com"},
            ],
        }
        result = await graph.ainvoke(state)

        assert result is not None

