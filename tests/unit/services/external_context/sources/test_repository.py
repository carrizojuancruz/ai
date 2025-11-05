"""Tests for external_context/sources/repository.py - external sources pagination and mapping."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.external_context.sources.models import (
    APIResponse,
    APISourceResponse,
    ExternalSource,
)
from app.services.external_context.sources.repository import ExternalSourcesRepository


@pytest.fixture
def repository():
    """Create repository instance for testing."""
    return ExternalSourcesRepository()


@pytest.fixture
def mock_api_source():
    """Create a mock API source response."""
    return APISourceResponse(
        id="src-123",
        name="Test Source",
        type_id="type-1",
        category_id="cat-1",
        url="https://example.com",
        description="Test description",
        include_path_patterns="/docs/**",
        exclude_path_patterns="/private/**",
        total_max_pages=50,
        recursion_depth=3,
        enabled=True,
        source_type_ref={"name": "documentation"},
        category_ref={"name": "technical"},
    )


class TestMapApiToExternalSource:
    """Test API response mapping to ExternalSource model."""

    def test_maps_all_fields_correctly(self, repository, mock_api_source):
        """Should map all fields from API response to ExternalSource."""
        result = repository._map_api_to_external_source(mock_api_source)

        assert isinstance(result, ExternalSource)
        assert result.name == "Test Source"
        assert result.type == "documentation"
        assert result.category == "technical"
        assert result.url == "https://example.com"
        assert result.description == "Test description"
        assert result.include_path_patterns == "/docs/**"
        assert result.exclude_path_patterns == "/private/**"
        assert result.total_max_pages == 50
        assert result.recursion_depth == 3
        assert result.enabled is True

    def test_handles_none_optional_fields(self, repository, mock_api_source):
        """Should handle None values for optional fields."""
        mock_api_source.description = None
        mock_api_source.include_path_patterns = None
        mock_api_source.exclude_path_patterns = None
        mock_api_source.total_max_pages = None
        mock_api_source.recursion_depth = None

        result = repository._map_api_to_external_source(mock_api_source)

        assert result.description == ""
        assert result.include_path_patterns == ""
        assert result.exclude_path_patterns == ""
        assert result.total_max_pages is None
        assert result.recursion_depth is None

    def test_extracts_nested_ref_names(self, repository, mock_api_source):
        """Should extract names from nested ref objects."""
        mock_api_source.source_type_ref = {"id": "type-1", "name": "API"}
        mock_api_source.category_ref = {"id": "cat-1", "name": "Integration"}

        result = repository._map_api_to_external_source(mock_api_source)

        assert result.type == "API"
        assert result.category == "Integration"

    def test_handles_empty_ref_dicts(self, repository, mock_api_source):
        """Should default to empty string when ref names missing."""
        mock_api_source.source_type_ref = {}
        mock_api_source.category_ref = {}

        result = repository._map_api_to_external_source(mock_api_source)

        assert result.type == ""
        assert result.category == ""


class TestGetAll:
    """Test get_all pagination and aggregation logic."""

    @pytest.mark.asyncio
    async def test_single_page_response(self, repository, mock_api_source):
        """Should fetch single page when all results fit in one page."""
        api_response = APIResponse(
            items=[mock_api_source],
            total=1,
            page=1,
            page_size=10,
        )

        with patch.object(repository.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = api_response.model_dump()

            result = await repository.get_all()

            assert len(result) == 1
            assert result[0].name == "Test Source"
            mock_get.assert_awaited_once_with("/internal/kb-sources", {"page": 1})

    @pytest.mark.asyncio
    async def test_multiple_pages_pagination(self, repository, mock_api_source):
        """Should fetch all pages until total reached."""
        source1 = mock_api_source.model_copy(update={"name": "Source 1"})
        source2 = mock_api_source.model_copy(update={"name": "Source 2"})
        source3 = mock_api_source.model_copy(update={"name": "Source 3"})

        page1_response = APIResponse(items=[source1, source2], total=3, page=1, page_size=2)
        page2_response = APIResponse(items=[source3], total=3, page=2, page_size=2)

        with patch.object(repository.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [
                page1_response.model_dump(),
                page2_response.model_dump(),
            ]

            result = await repository.get_all()

            assert len(result) == 3
            assert result[0].name == "Source 1"
            assert result[1].name == "Source 2"
            assert result[2].name == "Source 3"
            assert mock_get.await_count == 2

    @pytest.mark.asyncio
    async def test_stops_pagination_when_complete(self, repository, mock_api_source):
        """Should stop pagination when total reached or empty items received."""
        source1 = mock_api_source.model_copy(update={"name": "Source 1"})
        source2 = mock_api_source.model_copy(update={"name": "Source 2"})

        # Scenario: All items fit in first page
        complete_response = APIResponse(items=[source1, source2], total=2, page=1, page_size=2)

        with patch.object(repository.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = complete_response.model_dump()

            result = await repository.get_all()

            assert len(result) == 2
            mock_get.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_response_returns_empty_list(self, repository):
        """Should return empty list when API returns no sources."""
        api_response = APIResponse(items=[], total=0, page=1, page_size=10)

        with patch.object(repository.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = api_response.model_dump()

            result = await repository.get_all()

            assert result == []

    @pytest.mark.asyncio
    async def test_connection_error_when_none_response(self, repository):
        """Should raise ConnectionError when client returns None."""
        with patch.object(repository.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            with pytest.raises(ConnectionError, match="Failed to connect to external sources API"):
                await repository.get_all()

    @pytest.mark.asyncio
    async def test_stops_on_empty_dict_response(self, repository):
        """Should stop pagination when empty dict received."""
        with patch.object(repository.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {}

            result = await repository.get_all()

            assert result == []

    @pytest.mark.asyncio
    async def test_raises_on_invalid_response_structure(self, repository):
        """Should raise exception when response doesn't match APIResponse schema."""
        invalid_response = {"invalid": "structure"}

        with patch.object(repository.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = invalid_response

            with pytest.raises((ValueError, KeyError, TypeError)):
                await repository.get_all()

    @pytest.mark.asyncio
    async def test_multiple_pages_aggregation(self, repository, mock_api_source):
        """Should aggregate sources from multiple pages correctly."""
        sources_page1 = [
            mock_api_source.model_copy(update={"name": f"Source {i}"}) for i in range(1, 6)
        ]
        sources_page2 = [
            mock_api_source.model_copy(update={"name": f"Source {i}"}) for i in range(6, 11)
        ]
        sources_page3 = [
            mock_api_source.model_copy(update={"name": f"Source {i}"}) for i in range(11, 13)
        ]

        page1 = APIResponse(items=sources_page1, total=12, page=1, page_size=5)
        page2 = APIResponse(items=sources_page2, total=12, page=2, page_size=5)
        page3 = APIResponse(items=sources_page3, total=12, page=3, page_size=5)

        with patch.object(repository.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [
                page1.model_dump(),
                page2.model_dump(),
                page3.model_dump(),
            ]

            result = await repository.get_all()

            assert len(result) == 12
            assert result[0].name == "Source 1"
            assert result[5].name == "Source 6"
            assert result[11].name == "Source 12"
            # Verify page increments
            calls = mock_get.await_args_list
            assert calls[0][0] == ("/internal/kb-sources", {"page": 1})
            assert calls[1][0] == ("/internal/kb-sources", {"page": 2})
            assert calls[2][0] == ("/internal/kb-sources", {"page": 3})
