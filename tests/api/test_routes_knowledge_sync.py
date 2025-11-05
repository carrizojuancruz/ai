"""Unit tests for single-source sync endpoint."""

from unittest.mock import AsyncMock, patch

import pytest

from app.api.schemas.knowledge import SyncSourceRequest


@pytest.mark.asyncio
async def test_sync_new_source_success():
    """Test syncing a new source successfully."""
    from app.api.routes_knowledge import sync_single_source

    request = SyncSourceRequest(
        url="https://example.com/docs",
        name="Example Docs",
        total_max_pages=50
    )

    mock_result = {
        "success": True,
        "is_new_source": True,
        "documents_added": 120,
        "documents_processed": 25,
        "processing_time_seconds": 45.5,
        "message": "Successfully synchronized source"
    }

    with patch('app.api.routes_knowledge.KnowledgeService') as MockService:
        mock_instance = MockService.return_value
        mock_instance.upsert_source = AsyncMock(return_value=mock_result)

        response = await sync_single_source(request)

        assert response.success is True
        assert response.is_new_source is True
        assert response.documents_added == 120
        assert response.documents_processed == 25
        assert response.content_changed is True
        assert response.error is None


@pytest.mark.asyncio
async def test_sync_existing_source_no_changes():
    """Test syncing existing source with no content changes."""
    from app.api.routes_knowledge import sync_single_source

    request = SyncSourceRequest(
        url="https://example.com/docs",
        force_reindex=False
    )

    mock_result = {
        "success": True,
        "is_new_source": False,
        "documents_added": 0,
        "documents_processed": 25,
        "processing_time_seconds": 12.3,
        "message": "No changes detected"
    }

    with patch('app.api.routes_knowledge.KnowledgeService') as MockService:
        mock_instance = MockService.return_value
        mock_instance.upsert_source = AsyncMock(return_value=mock_result)

        response = await sync_single_source(request)

        assert response.success is True
        assert response.is_new_source is False
        assert response.documents_added == 0
        assert response.content_changed is False
        assert response.message == "No changes detected"


@pytest.mark.asyncio
async def test_sync_force_reindex():
    """Test force reindex overwrites existing source."""
    from app.api.routes_knowledge import sync_single_source

    request = SyncSourceRequest(
        url="https://example.com/docs",
        force_reindex=True
    )

    mock_result = {
        "success": True,
        "is_new_source": False,
        "documents_added": 120,
        "documents_processed": 25,
        "processing_time_seconds": 50.0,
        "message": "Successfully synchronized source"
    }

    with patch('app.api.routes_knowledge.KnowledgeService') as MockService:
        mock_instance = MockService.return_value
        mock_instance.upsert_source = AsyncMock(return_value=mock_result)

        response = await sync_single_source(request)

        assert response.success is True
        assert response.documents_added == 120
        mock_instance.upsert_source.assert_called_once()


@pytest.mark.asyncio
async def test_sync_crawl_error():
    """Test handling of crawl errors."""
    from app.api.routes_knowledge import sync_single_source

    request = SyncSourceRequest(url="https://example.com/404")

    mock_result = {
        "success": True,
        "documents_added": 0,
        "documents_processed": 0,
        "processing_time_seconds": 5.0,
        "message": "Failed to crawl source: 404 Not Found",
        "crawl_error": "404 Not Found"
    }

    with patch('app.api.routes_knowledge.KnowledgeService') as MockService:
        mock_instance = MockService.return_value
        mock_instance.upsert_source = AsyncMock(return_value=mock_result)

        response = await sync_single_source(request)

        assert response.success is True
        assert response.crawl_error == "404 Not Found"
        assert response.documents_added == 0


@pytest.mark.asyncio
async def test_sync_auto_generate_name():
    """Test auto-generation of source name from URL."""
    from app.api.routes_knowledge import sync_single_source

    request = SyncSourceRequest(
        url="https://docs.python.org/3/",
        name=None  # No name provided
    )

    mock_result = {
        "success": True,
        "is_new_source": True,
        "documents_added": 50,
        "documents_processed": 10,
        "processing_time_seconds": 30.0
    }

    with patch('app.api.routes_knowledge.KnowledgeService') as MockService:
        mock_instance = MockService.return_value
        mock_instance.upsert_source = AsyncMock(return_value=mock_result)

        await sync_single_source(request)

        # Check that Source was created with auto-generated name
        call_args = mock_instance.upsert_source.call_args[0][0]
        assert "docs.python.org" in call_args.name


@pytest.mark.asyncio
async def test_sync_with_custom_config():
    """Test sync with custom crawl configuration."""
    from app.api.routes_knowledge import sync_single_source

    request = SyncSourceRequest(
        url="https://example.com",
        total_max_pages=100,
        recursion_depth=5,
        include_path_patterns="/docs/.*",
        exclude_path_patterns="/admin/.*"
    )

    mock_result = {
        "success": True,
        "is_new_source": True,
        "documents_added": 200,
        "documents_processed": 50,
        "processing_time_seconds": 120.0
    }

    with patch('app.api.routes_knowledge.KnowledgeService') as MockService:
        mock_instance = MockService.return_value
        mock_instance.upsert_source = AsyncMock(return_value=mock_result)

        await sync_single_source(request)

        # Verify Source was created with correct config
        call_args = mock_instance.upsert_source.call_args[0][0]
        assert call_args.total_max_pages == 100
        assert call_args.recursion_depth == 5
        assert call_args.include_path_patterns == "/docs/.*"
        assert call_args.exclude_path_patterns == "/admin/.*"


def test_sync_request_validation_max_pages():
    """Test validation of max_pages constraint."""
    # Valid range
    request = SyncSourceRequest(url="https://example.com", total_max_pages=50)
    assert request.total_max_pages == 50

    # Test boundary
    request = SyncSourceRequest(url="https://example.com", total_max_pages=1)
    assert request.total_max_pages == 1

    request = SyncSourceRequest(url="https://example.com", total_max_pages=1000)
    assert request.total_max_pages == 1000


def test_sync_request_validation_recursion_depth():
    """Test validation of recursion_depth constraint."""
    # Valid range
    request = SyncSourceRequest(url="https://example.com", recursion_depth=3)
    assert request.recursion_depth == 3

    # Test boundary
    request = SyncSourceRequest(url="https://example.com", recursion_depth=0)
    assert request.recursion_depth == 0

    request = SyncSourceRequest(url="https://example.com", recursion_depth=10)
    assert request.recursion_depth == 10


def test_sync_request_defaults():
    """Test default values for optional fields."""
    request = SyncSourceRequest(url="https://example.com")

    assert request.type == "External"
    assert request.category == "General"
    assert request.description == ""
    assert request.total_max_pages == 20
    assert request.recursion_depth == 2
    assert request.force_reindex is False
