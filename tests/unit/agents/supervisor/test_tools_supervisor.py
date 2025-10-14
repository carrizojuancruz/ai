"""Tests for app/agents/supervisor/tools.py"""

import json
from unittest.mock import AsyncMock

import pytest

from app.agents.supervisor.tools import knowledge_search_tool, query_knowledge_base


@pytest.mark.unit
class TestQueryKnowledgeBase:
    """Test suite for query_knowledge_base function."""

    @pytest.mark.asyncio
    async def test_query_knowledge_base_success(self, mock_knowledge_service):
        """Test successful knowledge base query."""
        query = "What is an emergency fund?"

        result = await query_knowledge_base(query)

        assert isinstance(result, str)
        mock_knowledge_service.search.assert_called_once_with(query)

    @pytest.mark.asyncio
    async def test_query_knowledge_base_returns_json_string(self, mock_knowledge_service):
        """Test that query_knowledge_base returns valid JSON string."""
        query = "budgeting tips"

        result = await query_knowledge_base(query)

        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 2

    @pytest.mark.asyncio
    async def test_query_knowledge_base_empty_results(self, mock_knowledge_service):
        """Test query with empty results."""
        mock_knowledge_service.search = AsyncMock(return_value=[])
        query = "nonexistent topic"

        result = await query_knowledge_base(query)

        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 0

    @pytest.mark.asyncio
    async def test_query_knowledge_base_handles_special_characters(self, mock_knowledge_service):
        """Test query with special characters."""
        query = "What's the 401(k) contribution limit?"

        result = await query_knowledge_base(query)

        parsed = json.loads(result)
        assert isinstance(parsed, list)

    @pytest.mark.asyncio
    async def test_query_knowledge_base_json_serialization(self, mock_knowledge_service):
        """Test proper JSON serialization with ensure_ascii=False."""
        mock_knowledge_service.search = AsyncMock(
            return_value=[
                {
                    "content": "Información sobre presupuestos",
                    "source": "https://example.com/es",
                    "score": 0.9,
                }
            ]
        )
        query = "presupuesto"

        result = await query_knowledge_base(query)

        parsed = json.loads(result)
        assert "Información" in parsed[0]["content"]

    @pytest.mark.asyncio
    async def test_query_knowledge_base_with_complex_results(self, mock_knowledge_service):
        """Test query with complex nested results."""
        mock_knowledge_service.search = AsyncMock(
            return_value=[
                {
                    "content": "Main content",
                    "source": "https://example.com",
                    "score": 0.95,
                    "metadata": {"author": "Test", "date": "2025-01-01"},
                }
            ]
        )
        query = "test"

        result = await query_knowledge_base(query)

        parsed = json.loads(result)
        assert "metadata" in parsed[0]
        assert parsed[0]["metadata"]["author"] == "Test"


@pytest.mark.unit
class TestKnowledgeSearchTool:
    """Test suite for knowledge_search_tool."""

    def test_tool_has_correct_name(self):
        """Test that tool has the correct name."""
        assert knowledge_search_tool.name == "query_knowledge_base"

    def test_tool_has_description(self):
        """Test that tool has a description."""
        assert knowledge_search_tool.description is not None
        assert len(knowledge_search_tool.description) > 0

    def test_tool_description_mentions_knowledge_base(self):
        """Test that tool description mentions knowledge base."""
        description = knowledge_search_tool.description.lower()
        assert "knowledge base" in description or "knowledge" in description

    def test_tool_description_mentions_search(self):
        """Test that tool description mentions search functionality."""
        description = knowledge_search_tool.description.lower()
        assert "search" in description

    def test_tool_is_async(self):
        """Test that tool is configured for async execution."""
        assert knowledge_search_tool.coroutine is not None

    @pytest.mark.asyncio
    async def test_tool_invocation(self, mock_knowledge_service):
        """Test that tool can be invoked successfully."""
        query = "financial planning"

        result = await knowledge_search_tool.ainvoke({"query": query})

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    @pytest.mark.asyncio
    async def test_tool_with_empty_query(self, mock_knowledge_service):
        """Test tool with empty query string."""
        query = ""

        result = await knowledge_search_tool.ainvoke({"query": query})

        parsed = json.loads(result)
        assert isinstance(parsed, list)

    @pytest.mark.asyncio
    async def test_tool_handles_service_errors_gracefully(self, mock_knowledge_service, mocker):
        """Test that tool handles service errors gracefully."""
        mock_knowledge_service.search = AsyncMock(side_effect=Exception("Service error"))

        query = "test query"

        with pytest.raises(Exception, match="Service error"):
            await knowledge_search_tool.ainvoke({"query": query})
