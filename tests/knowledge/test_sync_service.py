from unittest.mock import AsyncMock, MagicMock

import pytest

from app.knowledge.models import Source
from app.knowledge.sync_service import KnowledgeBaseSyncService


@pytest.mark.unit
class TestKnowledgeBaseSyncService:

    @pytest.fixture
    def mock_external_repository(self, mocker):
        mock = mocker.patch(
            'app.knowledge.sync_service.ExternalSourcesRepository'
        )
        mock_instance = AsyncMock()
        mock_instance.get_all.return_value = []
        mock.return_value = mock_instance
        return mock_instance

    @pytest.fixture
    def mock_knowledge_service(self, mocker):
        mock = mocker.patch('app.knowledge.sync_service.KnowledgeService')
        mock_instance = MagicMock()
        mock_instance.get_sources.return_value = []
        mock_instance.upsert_source = AsyncMock(return_value={
            "success": True,
            "is_new_source": True,
            "documents_added": 10
        })
        mock_instance.delete_source.return_value = {"success": True}
        mock.return_value = mock_instance
        return mock_instance

    @pytest.fixture
    def mock_crawl_logger(self, mocker):
        mock = mocker.patch('app.knowledge.sync_service.CrawlLogger')
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        return mock_instance

    @pytest.fixture
    def sync_service(
        self,
        mock_external_repository,
        mock_knowledge_service,
        mock_crawl_logger
    ):
        return KnowledgeBaseSyncService()

    @pytest.mark.asyncio
    async def test_sync_all_creates_new_sources(
        self,
        sync_service,
        mock_external_repository,
        mock_knowledge_service
    ):


        external_sources = [
            Source(id=f"s{i}", name=f"Source {i}", url=f"https://example{i}.com")
            for i in range(3)
        ]
        mock_external_repository.get_all.return_value = external_sources

        result = await sync_service.sync_all()

        assert result["sources_created"] == 3
        assert result["sources_updated"] == 0
        assert mock_knowledge_service.upsert_source.call_count == 3

    @pytest.mark.asyncio
    async def test_sync_all_updates_existing_sources(
        self,
        sync_service,
        mock_external_repository,
        mock_knowledge_service
    ):


        external_sources = [
            Source(id="s1", name="Source 1", url="https://example.com")
        ]
        existing_sources = [
            Source(id="s1", name="Source 1", url="https://example.com")
        ]

        mock_external_repository.get_all.return_value = external_sources
        mock_knowledge_service.get_sources.return_value = existing_sources
        mock_knowledge_service.upsert_source.return_value = {
            "success": True,
            "is_new_source": False,
            "documents_added": 5
        }

        result = await sync_service.sync_all()

        assert result["sources_updated"] == 1
        assert result["sources_created"] == 0

    @pytest.mark.asyncio
    async def test_sync_all_deletes_obsolete_sources(
        self,
        sync_service,
        mock_external_repository,
        mock_knowledge_service
    ):


        external_sources = [
            Source(id="s1", name="Source 1", url="https://example1.com")
        ]
        existing_sources = [
            Source(id="s1", name="Source 1", url="https://example1.com"),
            Source(id="s2", name="Source 2", url="https://example2.com")
        ]

        mock_external_repository.get_all.return_value = external_sources
        mock_knowledge_service.get_sources.return_value = existing_sources

        result = await sync_service.sync_all()

        assert result["sources_deleted"] == 1
        mock_knowledge_service.delete_source.assert_called_once_with(
            "https://example2.com"
        )

    @pytest.mark.asyncio
    async def test_sync_all_handles_crawl_errors(
        self,
        sync_service,
        mock_external_repository,
        mock_knowledge_service
    ):


        external_sources = [
            Source(id="s1", name="Source 1", url="https://example.com")
        ]

        mock_external_repository.get_all.return_value = external_sources
        mock_knowledge_service.upsert_source.return_value = {
            "success": True,
            "crawl_error": "SSL certificate error"
        }

        result = await sync_service.sync_all()

        assert result["sources_errors"] == 1
        assert len(result["sync_failures"]) == 1

    @pytest.mark.asyncio
    async def test_sync_all_with_limit(
        self,
        sync_service,
        mock_external_repository,
        mock_knowledge_service
    ):


        external_sources = [
            Source(id=f"s{i}", name=f"Source {i}", url=f"https://example{i}.com")
            for i in range(10)
        ]
        mock_external_repository.get_all.return_value = external_sources

        result = await sync_service.sync_all(limit=3)

        assert mock_knowledge_service.upsert_source.call_count == 3
        assert result["sources_created"] >= 0

    @pytest.mark.asyncio
    async def test_sync_all_respects_enabled_flag(
        self,
        sync_service,
        mock_external_repository,
        mock_knowledge_service
    ):


        external_sources = [
            Source(id="s1", name="Source 1", url="https://example1.com", enabled=True),
            Source(id="s2", name="Source 2", url="https://example2.com", enabled=False),
            Source(id="s3", name="Source 3", url="https://example3.com", enabled=True)
        ]
        mock_external_repository.get_all.return_value = external_sources

        result = await sync_service.sync_all()

        assert mock_knowledge_service.upsert_source.call_count == 2
        assert result["sources_created"] >= 0

    @pytest.mark.asyncio
    async def test_sync_all_external_api_unavailable(
        self,
        sync_service,
        mock_external_repository,
        mock_knowledge_service
    ):
        mock_external_repository.get_all.side_effect = Exception("API error")

        result = await sync_service.sync_all()

        assert result["external_sources_available"] is False
        assert result["deletions_skipped"] is True

    @pytest.mark.asyncio
    async def test_sync_all_tracks_total_chunks(
        self,
        sync_service,
        mock_external_repository,
        mock_knowledge_service
    ):


        external_sources = [
            Source(id=f"s{i}", name=f"Source {i}", url=f"https://example{i}.com")
            for i in range(3)
        ]
        mock_external_repository.get_all.return_value = external_sources

        upsert_results = [
            {"success": True, "is_new_source": True, "documents_added": 10},
            {"success": True, "is_new_source": True, "documents_added": 20},
            {"success": True, "is_new_source": True, "documents_added": 30}
        ]
        mock_knowledge_service.upsert_source.side_effect = upsert_results

        result = await sync_service.sync_all()

        assert result["total_chunks_created"] == 60

    @pytest.mark.asyncio
    async def test_sync_all_deletes_all_when_external_empty(
        self,
        sync_service,
        mock_external_repository,
        mock_knowledge_service
    ):
        mock_external_repository.get_all.return_value = []
        mock_knowledge_service.get_sources.return_value = [
            Source(id="s1", name="S1", url="https://ex1.com"),
            Source(id="s2", name="S2", url="https://ex2.com"),
        ]

        result = await sync_service.sync_all()

        assert result["sources_deleted"] == 2
        assert mock_knowledge_service.delete_source.call_count == 2

    @pytest.mark.asyncio
    async def test_sync_all_continues_on_upsert_exception(
        self,
        sync_service,
        mock_external_repository,
        mock_knowledge_service
    ):
        external_sources = [
            Source(id="s1", name="S1", url="https://ex1.com"),
            Source(id="s2", name="S2", url="https://ex2.com"),
            Source(id="s3", name="S3", url="https://ex3.com"),
        ]
        mock_external_repository.get_all.return_value = external_sources

        async def upsert_side_effect(source: Source):
            if source.url == "https://ex2.com":
                raise Exception("upsert failed")
            return {"success": True, "is_new_source": True, "documents_added": 1}

        mock_knowledge_service.upsert_source.side_effect = upsert_side_effect

        result = await sync_service.sync_all()

        assert result["sources_errors"] == 1
        assert len(result["sync_failures"]) == 1
        assert mock_knowledge_service.upsert_source.call_count == 3

    @pytest.mark.asyncio
    async def test_sync_all_deletions_skipped_false_when_external_ok(
        self,
        sync_service,
        mock_external_repository
    ):
        mock_external_repository.get_all.return_value = []
        result = await sync_service.sync_all()
        assert result["external_sources_available"] is True
        assert result["deletions_skipped"] is False

    @pytest.mark.asyncio
    async def test_sync_all_filters_before_limit(
        self,
        sync_service,
        mock_external_repository,
        mock_knowledge_service
    ):
        external_sources = [
            Source(id="s1", name="S1", url="https://ex1.com", enabled=False),
            Source(id="s2", name="S2", url="https://ex2.com", enabled=True),
            Source(id="s3", name="S3", url="https://ex3.com", enabled=False),
            Source(id="s4", name="S4", url="https://ex4.com", enabled=True),
        ]
        mock_external_repository.get_all.return_value = external_sources

        await sync_service.sync_all(limit=1)

        assert mock_knowledge_service.upsert_source.call_count == 1
        # Ensure the processed source was enabled
        processed_url = mock_knowledge_service.upsert_source.call_args.args[0].url
        assert processed_url in {"https://ex2.com", "https://ex4.com"}
