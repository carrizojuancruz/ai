"""Tests for app/agents/supervisor/wealth_agent/tools.py"""

import json
from unittest.mock import AsyncMock

import pytest

from app.agents.supervisor.wealth_agent.tools import search_kb


@pytest.mark.unit
class TestSearchKB:
    """Test suite for search_kb tool."""

    @pytest.mark.asyncio
    async def test_search_kb_returns_json_string(self, mock_knowledge_service):
        """Test search_kb returns JSON string."""
        result = await search_kb.ainvoke({"query": "emergency fund"})

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    @pytest.mark.asyncio
    async def test_search_kb_formats_results_correctly(self, mock_knowledge_service):
        """Test search_kb formats results with all required fields."""
        result = await search_kb.ainvoke({"query": "emergency fund"})

        parsed = json.loads(result)
        assert len(parsed) > 0

        first_result = parsed[0]
        assert "content" in first_result
        assert "source" in first_result
        assert "metadata" in first_result

    @pytest.mark.asyncio
    async def test_search_kb_includes_metadata(self, mock_knowledge_service):
        """Test search_kb includes complete metadata."""
        result = await search_kb.ainvoke({"query": "savings"})

        parsed = json.loads(result)
        metadata = parsed[0]["metadata"]

        assert "source_url" in metadata
        assert "section_url" in metadata
        assert "name" in metadata
        assert "type" in metadata
        assert "category" in metadata
        assert "description" in metadata

    @pytest.mark.asyncio
    async def test_search_kb_uses_section_url_as_source(self, mock_knowledge_service):
        """Test search_kb prefers section_url as source."""
        result = await search_kb.ainvoke({"query": "test"})

        parsed = json.loads(result)
        first_result = parsed[0]

        assert first_result["source"] == "https://example.com/emergency-fund#section1"

    @pytest.mark.asyncio
    async def test_search_kb_fallback_to_source_url(self, mock_knowledge_service):
        """Test search_kb falls back to source_url when section_url empty."""
        mock_knowledge_service.search = AsyncMock(
            return_value=[
                {
                    "content": "Test content",
                    "section_url": "",
                    "source_url": "https://example.com/article",
                    "name": "Test",
                    "type": "article",
                    "category": "Test",
                    "description": "Test description",
                }
            ]
        )

        result = await search_kb.ainvoke({"query": "test"})
        parsed = json.loads(result)

        assert parsed[0]["source"] == "https://example.com/article"

    @pytest.mark.asyncio
    async def test_search_kb_handles_empty_results(self, mock_knowledge_service):
        """Test search_kb handles empty search results."""
        mock_knowledge_service.search = AsyncMock(return_value=[])

        result = await search_kb.ainvoke({"query": "nonexistent"})
        parsed = json.loads(result)

        assert isinstance(parsed, list)
        assert len(parsed) == 0

    @pytest.mark.asyncio
    async def test_search_kb_handles_service_error(self, mock_knowledge_service):
        """Test search_kb handles knowledge service errors."""
        mock_knowledge_service.search = AsyncMock(
            side_effect=Exception("Service unavailable")
        )

        result = await search_kb.ainvoke({"query": "test"})
        parsed = json.loads(result)

        assert isinstance(parsed, list)
        assert len(parsed) > 0
        assert "source" in parsed[0]
        error_info = parsed[0]["source"]
        assert "SEARCH_FAILED" in str(error_info)

    @pytest.mark.asyncio
    async def test_search_kb_filters_incomplete_results(self, mock_knowledge_service):
        """Test search_kb filters results without content or source."""
        mock_knowledge_service.search = AsyncMock(
            return_value=[
                {
                    "content": "Valid content",
                    "source_url": "https://example.com/valid",
                    "section_url": "",
                    "name": "Valid",
                    "type": "article",
                    "category": "Test",
                    "description": "Valid",
                },
                {
                    "content": "",
                    "source_url": "https://example.com/invalid",
                    "section_url": "",
                    "name": "Invalid",
                    "type": "article",
                    "category": "Test",
                    "description": "Invalid",
                },
                {
                    "content": "Another valid",
                    "source_url": "",
                    "section_url": "",
                    "name": "No source",
                    "type": "article",
                    "category": "Test",
                    "description": "No source",
                },
            ]
        )

        result = await search_kb.ainvoke({"query": "test"})
        parsed = json.loads(result)

        # The tool filters out results without content, but includes results with content even if source_url is empty
        assert len(parsed) == 2
        assert parsed[0]["content"] == "Valid content"
        assert parsed[1]["content"] == "Another valid"

    @pytest.mark.asyncio
    async def test_search_kb_preserves_unicode(self, mock_knowledge_service):
        """Test search_kb preserves unicode characters."""
        mock_knowledge_service.search = AsyncMock(
            return_value=[
                {
                    "content": "Información financiera en español",
                    "source_url": "https://example.com/es",
                    "section_url": "",
                    "name": "Guía Financiera",
                    "type": "article",
                    "category": "Español",
                    "description": "Descripción en español",
                }
            ]
        )

        result = await search_kb.ainvoke({"query": "español"})
        parsed = json.loads(result)

        assert "Información" in parsed[0]["content"]
        assert "Guía" in parsed[0]["metadata"]["name"]

    @pytest.mark.asyncio
    async def test_search_kb_tool_has_description(self):
        """Test search_kb tool has proper description."""
        assert hasattr(search_kb, "description")
        assert "knowledge base" in search_kb.description.lower()

    @pytest.mark.asyncio
    async def test_search_kb_with_complex_query(self, mock_knowledge_service):
        """Test search_kb with complex multi-word query."""
        query = "how to build an emergency fund for retirement"

        result = await search_kb.ainvoke({"query": query})
        parsed = json.loads(result)

        assert isinstance(parsed, list)
        mock_knowledge_service.search.assert_called_once_with(query, filter={'content_source': 'external'})
