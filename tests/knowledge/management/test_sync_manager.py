import pytest


@pytest.mark.unit
class TestKbSyncManager:

    def test_lazy_sync_service_initialization(self, sync_manager):
        assert sync_manager._sync_service is None

    @pytest.mark.asyncio
    async def test_sync_all_success(self, sync_manager, mock_sync_service):
        mock_sync_service.sync_all.return_value = {
            "sources_created": 3,
            "sources_updated": 2,
            "sources_deleted": 1
        }

        result = await sync_manager.sync_all()

        assert result["sources_created"] == 3
        assert result["sources_updated"] == 2
        assert result["sources_deleted"] == 1
        mock_sync_service.sync_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_all_exception(self, sync_manager, mock_sync_service):
        mock_sync_service.sync_all.side_effect = Exception("Sync error")

        with pytest.raises(Exception, match="Sync error"):
            await sync_manager.sync_all()

    @pytest.mark.asyncio
    async def test_upsert_source_by_url_full(self, sync_manager, mock_kb_service):
        mock_kb_service.upsert_source.return_value = {"success": True}

        result = await sync_manager.upsert_source_by_url(
            url="https://example.com",
            name="Test Source",
            source_type="article",
            category="finance",
            description="Test description",
            max_pages=50,
            recursion_depth=3
        )

        assert result["success"] is True
        call_args = mock_kb_service.upsert_source.call_args
        source = call_args[0][0]
        assert source.name == "Test Source"
        assert source.type == "article"

    @pytest.mark.asyncio
    async def test_upsert_source_by_url_success(self, sync_manager, mock_kb_service):
        mock_kb_service.upsert_source.return_value = {
            "success": True,
            "documents_added": 25
        }

        result = await sync_manager.upsert_source_by_url("https://example.com")

        assert result["success"] is True
        assert result["documents_added"] == 25

    @pytest.mark.asyncio
    async def test_upsert_source_by_url_failure(self, sync_manager, mock_kb_service):
        mock_kb_service.upsert_source.return_value = {
            "success": False,
            "error": "Crawl failed"
        }

        result = await sync_manager.upsert_source_by_url("https://example.com")

        assert result["success"] is False
        assert result["error"] == "Crawl failed"

    @pytest.mark.asyncio
    async def test_upsert_source_by_url_exception(self, sync_manager, mock_kb_service):
        mock_kb_service.upsert_source.side_effect = Exception("Upsert error")

        result = await sync_manager.upsert_source_by_url("https://example.com")

        assert result["success"] is False
        assert "error" in result
