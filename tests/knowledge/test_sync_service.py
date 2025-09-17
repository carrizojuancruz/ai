from dataclasses import dataclass
from unittest.mock import AsyncMock, Mock

import pytest

from app.knowledge.sync_service import KnowledgeBaseSyncService


@dataclass
class MockExternalSource:
    url: str
    name: str
    enable: bool
    type: str
    category: str
    description: str
    include_path_patterns: str
    exclude_path_patterns: str
    total_max_pages: int
    recursion_depth: int


class TestKnowledgeBaseSyncService:

    @pytest.fixture
    def sync_service(self, mock_external_services):
        return KnowledgeBaseSyncService()

    @pytest.fixture
    def mock_external_sources(self):
        return [
            MockExternalSource(
                url="https://example1.com",
                name="External Source 1",
                enable=True,
                type="web",
                category="finance",
                description="Test description 1",
                include_path_patterns="",
                exclude_path_patterns="",
                total_max_pages=10,
                recursion_depth=1
            ),
            MockExternalSource(
                url="https://example2.com",
                name="External Source 2",
                enable=True,
                type="web",
                category="investment",
                description="Test description 2",
                include_path_patterns="",
                exclude_path_patterns="",
                total_max_pages=15,
                recursion_depth=2
            )
        ]

    @pytest.fixture
    def mock_kb_sources(self, sample_source):
        return [
            sample_source,
            Mock(
                id="internal-only",
                url="https://internal-only.com",
                name="Internal Only Source",
                type="web",
                category="internal"
            )
        ]

    @pytest.mark.asyncio
    async def test_sync_external_has_more_sources(self, sync_service, mock_external_sources):
        sync_service.external_repo.get_all = AsyncMock(return_value=mock_external_sources)
        sync_service.kb_service.get_sources = Mock(return_value=[])
        sync_service.kb_service.upsert_source = AsyncMock(return_value={
            "success": True,
            "is_new_source": True,
            "documents_added": 5,
            "documents_processed": 10
        })

        result = await sync_service.sync_all()

        assert result["sources_created"] == 2
        assert result["sources_updated"] == 0
        assert result["sources_deleted"] == 0
        assert result["total_chunks_created"] == 10

    @pytest.mark.asyncio
    async def test_sync_internal_has_more_sources(self, sync_service, mock_kb_sources):
        sync_service.external_repo.get_all = AsyncMock(return_value=[])
        sync_service.kb_service.get_sources = Mock(return_value=mock_kb_sources)
        sync_service.kb_service.delete_source_by_url = AsyncMock(return_value=True)

        result = await sync_service.sync_all()

        assert result["sources_created"] == 0
        assert result["sources_deleted"] == 2
        assert result["sources_no_changes"] == 0

    @pytest.mark.asyncio
    async def test_sync_mixed_sources_scenario(self, sync_service, mock_external_sources, sample_source):
        mock_external_sources[0].url = sample_source.url

        sync_service.external_repo.get_all = AsyncMock(return_value=mock_external_sources)
        sync_service.kb_service.get_sources = Mock(return_value=[
            sample_source,
            Mock(url="https://internal-only.com", id="internal-only")
        ])

        def mock_upsert_response(source):
            if source.url == sample_source.url:
                return {
                    "success": True,
                    "is_new_source": False,
                    "documents_added": 3,
                    "documents_processed": 8
                }
            else:
                return {
                    "success": True,
                    "is_new_source": True,
                    "documents_added": 7,
                    "documents_processed": 12
                }

        sync_service.kb_service.upsert_source = AsyncMock(side_effect=mock_upsert_response)
        sync_service.kb_service.delete_source_by_url = AsyncMock(return_value=True)

        result = await sync_service.sync_all()

        assert result["sources_created"] == 1
        assert result["sources_updated"] == 1
        assert result["sources_deleted"] == 1

    @pytest.mark.asyncio
    async def test_sync_no_content_changes(self, sync_service, mock_external_sources):
        sync_service.external_repo.get_all = AsyncMock(return_value=mock_external_sources)
        sync_service.kb_service.get_sources = Mock(return_value=[])
        sync_service.kb_service.upsert_source = AsyncMock(return_value={
            "success": True,
            "is_new_source": False,
            "documents_added": 0,
            "documents_processed": 5,
            "message": "Content hash matched - no changes detected"
        })

        result = await sync_service.sync_all()

        assert result["sources_no_changes"] == 2
        assert result["sources_updated"] == 0
        assert result["total_chunks_created"] == 0

    @pytest.mark.asyncio
    async def test_sync_with_crawling_errors(self, sync_service, mock_external_sources):
        sync_service.external_repo.get_all = AsyncMock(return_value=mock_external_sources)
        sync_service.kb_service.get_sources = Mock(return_value=[])

        def mock_upsert_responses(source):
            if "example1" in source.url:
                return {
                    "success": True,
                    "is_new_source": True,
                    "documents_added": 3,
                    "documents_processed": 5
                }
            else:
                return {
                    "success": True,
                    "is_new_source": True,
                    "documents_added": 0,
                    "documents_processed": 0,
                    "crawl_error": "SSL certificate verification failed"
                }

        sync_service.kb_service.upsert_source = AsyncMock(side_effect=mock_upsert_responses)

        result = await sync_service.sync_all()

        assert result["sources_created"] == 2
        assert result["sources_errors"] == 0
        assert len(result.get("sync_failures", [])) == 0

    @pytest.mark.asyncio
    async def test_sync_disabled_sources_skipped(self, sync_service, mock_external_sources):
        mock_external_sources[0].enable = False

        sync_service.external_repo.get_all = AsyncMock(return_value=mock_external_sources)
        sync_service.kb_service.get_sources = Mock(return_value=[])
        sync_service.kb_service.upsert_source = AsyncMock(return_value={
            "success": True,
            "is_new_source": True,
            "documents_added": 5
        })

        result = await sync_service.sync_all()

        assert result["sources_created"] == 1
        sync_service.kb_service.upsert_source.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_with_processing_limit(self, sync_service, mock_external_sources):
        more_sources = mock_external_sources + [
            MockExternalSource(url="https://example3.com", name="Source 3", enable=True, type="web", category="test", description="desc", include_path_patterns="", exclude_path_patterns="", total_max_pages=10, recursion_depth=1),
            MockExternalSource(url="https://example4.com", name="Source 4", enable=True, type="web", category="test", description="desc", include_path_patterns="", exclude_path_patterns="", total_max_pages=10, recursion_depth=1)
        ]

        sync_service.external_repo.get_all = AsyncMock(return_value=more_sources)
        sync_service.kb_service.get_sources = Mock(return_value=[])
        sync_service.kb_service.upsert_source = AsyncMock(return_value={
            "success": True,
            "is_new_source": True,
            "documents_added": 2
        })

        result = await sync_service.sync_all(limit=2)

        assert result["sources_created"] == 2
        assert sync_service.kb_service.upsert_source.call_count == 2

    @pytest.mark.asyncio
    async def test_sync_all_external_api_failure(self, sync_service):
        sync_service.external_repo.get_all = AsyncMock(side_effect=Exception("API Error"))
        sync_service.kb_service.get_sources = Mock(return_value=[])

        result = await sync_service.sync_all()

        assert not result["external_sources_available"]
        assert "sources_errors" in result
