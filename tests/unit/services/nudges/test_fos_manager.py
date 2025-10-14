from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.nudges.fos_manager import FOSNudgeManager, FOSNudgeStats
from app.services.nudges.models import NudgeMessage


@pytest.fixture
def manager():
    return FOSNudgeManager()


@pytest.fixture
def nudge_message():
    return NudgeMessage(
        user_id=uuid4(),
        nudge_type="test_nudge",
        priority=1,
        payload={
            "notification_text": "Test notification",
            "preview_text": "Test preview",
            "metadata": {
                "topic": "test_topic",
                "memory_id": "mem_123",
                "importance": 5,
                "memory_text": "Test memory"
            }
        },
        channel="app"
    )


@pytest.fixture
def nudge_response():
    return {
        "id": str(uuid4()),
        "user_id": str(uuid4()),
        "nudge_type": "test_nudge",
        "notification_text": "Test notification",
        "preview_text": "Test preview",
        "topic": "test_topic",
        "memory_id": "mem_123",
        "importance": "high",
        "memory_text": "Test memory",
        "priority": 1,
        "status": "pending",
        "channel": "app",
        "created_at": datetime.now(timezone.utc).isoformat()
    }


class TestFOSNudgeManager:
    @pytest.mark.asyncio
    async def test_initialization(self, manager):
        assert manager.fos_client is not None

    @pytest.mark.asyncio
    async def test_enqueue_nudge_success(self, manager, nudge_message):
        mock_response = {"id": "nudge_123"}
        manager.fos_client.post = AsyncMock(return_value=mock_response)

        result = await manager.enqueue_nudge(nudge_message)

        assert result == "nudge_123"
        manager.fos_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_enqueue_nudge_no_response(self, manager, nudge_message):
        manager.fos_client.post = AsyncMock(return_value=None)

        with pytest.raises(Exception, match="FOS service request failed"):
            await manager.enqueue_nudge(nudge_message)

    @pytest.mark.asyncio
    async def test_enqueue_nudge_no_id_in_response(self, manager, nudge_message):
        manager.fos_client.post = AsyncMock(return_value={"status": "ok"})

        with pytest.raises(ValueError, match="FOS service did not return valid ID"):
            await manager.enqueue_nudge(nudge_message)

    @pytest.mark.asyncio
    async def test_get_pending_nudges_success(self, manager, nudge_response):
        user_id = uuid4()
        mock_response = {"nudges": [nudge_response]}
        manager.fos_client.get = AsyncMock(return_value=mock_response)

        result = await manager.get_pending_nudges(user_id)

        assert len(result) == 1
        assert result[0].nudge_type == "test_nudge"

    @pytest.mark.asyncio
    async def test_get_pending_nudges_with_filters(self, manager, nudge_response):
        user_id = uuid4()
        mock_response = {"nudges": [nudge_response]}
        manager.fos_client.get = AsyncMock(return_value=mock_response)

        result = await manager.get_pending_nudges(
            user_id,
            nudge_type="test_nudge",
            status=["pending", "processing"],
            limit=10
        )

        assert len(result) == 1
        call_args = manager.fos_client.get.call_args[0][0]
        assert "nudge_type=test_nudge" in call_args
        assert "limit=10" in call_args

    @pytest.mark.asyncio
    async def test_get_pending_nudges_no_response(self, manager):
        user_id = uuid4()
        manager.fos_client.get = AsyncMock(return_value=None)

        result = await manager.get_pending_nudges(user_id)

        assert result == []

    @pytest.mark.asyncio
    async def test_get_pending_nudges_invalid_data(self, manager):
        user_id = uuid4()
        invalid_nudge = {"invalid": "data"}
        mock_response = {"nudges": [invalid_nudge]}
        manager.fos_client.get = AsyncMock(return_value=mock_response)

        result = await manager.get_pending_nudges(user_id)

        assert result == []

    @pytest.mark.asyncio
    async def test_mark_processing_success(self, manager, nudge_response):
        nudge_ids = [uuid4()]
        mock_response = {"updated_nudges": [nudge_response]}
        manager.fos_client.patch = AsyncMock(return_value=mock_response)

        result = await manager.mark_processing(nudge_ids)

        assert len(result) == 1
        assert result[0].status == "pending"

    @pytest.mark.asyncio
    async def test_mark_processing_no_response(self, manager):
        nudge_ids = [uuid4()]
        manager.fos_client.patch = AsyncMock(return_value=None)

        result = await manager.mark_processing(nudge_ids)

        assert result == []

    @pytest.mark.asyncio
    async def test_complete_nudge_success(self, manager):
        nudge_id = uuid4()
        mock_response = {"updated_count": 1}
        manager.fos_client.patch = AsyncMock(return_value=mock_response)

        result = await manager.complete_nudge(nudge_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_complete_nudge_no_response(self, manager):
        nudge_id = uuid4()
        manager.fos_client.patch = AsyncMock(return_value=None)

        result = await manager.complete_nudge(nudge_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_complete_nudge_zero_updated(self, manager):
        nudge_id = uuid4()
        mock_response = {"updated_count": 0}
        manager.fos_client.patch = AsyncMock(return_value=mock_response)

        result = await manager.complete_nudge(nudge_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_get_queue_stats_success(self, manager):
        mock_response = {"pending_count": 5, "processing_count": 2, "total_count": 7}
        manager.fos_client.get = AsyncMock(return_value=mock_response)

        result = await manager.get_queue_stats()

        assert isinstance(result, FOSNudgeStats)
        assert result.pending_count == 5
        assert result.processing_count == 2
        assert result.total_count == 7

    @pytest.mark.asyncio
    async def test_get_queue_stats_with_user_id(self, manager):
        user_id = uuid4()
        mock_response = {"pending_count": 1, "processing_count": 0, "total_count": 1}
        manager.fos_client.get = AsyncMock(return_value=mock_response)

        result = await manager.get_queue_stats(user_id)

        assert result.pending_count == 1
        call_args = manager.fos_client.get.call_args[0][0]
        assert str(user_id) in call_args

    @pytest.mark.asyncio
    async def test_get_queue_stats_no_response(self, manager):
        manager.fos_client.get = AsyncMock(return_value=None)

        result = await manager.get_queue_stats()

        assert result.pending_count == 0
        assert result.processing_count == 0
        assert result.total_count == 0

    @pytest.mark.asyncio
    async def test_delete_nudges_by_memory_id_success(self, manager):
        memory_id = "mem_123"
        mock_response = {"memory_id": memory_id, "cancelled_count": 3, "cancelled_nudge_ids": ["n1", "n2", "n3"]}
        manager.fos_client.delete = AsyncMock(return_value=mock_response)

        result = await manager.delete_nudges_by_memory_id(memory_id)

        assert result["cancelled_count"] == 3
        assert len(result["cancelled_nudge_ids"]) == 3

    @pytest.mark.asyncio
    async def test_delete_nudges_by_memory_id_empty_id(self, manager):
        with pytest.raises(ValueError, match="memory_id cannot be empty"):
            await manager.delete_nudges_by_memory_id("")

    @pytest.mark.asyncio
    async def test_delete_nudges_by_memory_id_no_response(self, manager):
        memory_id = "mem_123"
        manager.fos_client.delete = AsyncMock(return_value=None)

        result = await manager.delete_nudges_by_memory_id(memory_id)

        assert result["cancelled_count"] == 0
        assert result["cancelled_nudge_ids"] == []

    @pytest.mark.asyncio
    async def test_bulk_delete_nudges_by_memory_ids_success(self, manager):
        memory_ids = ["mem_1", "mem_2"]
        mock_response = {"total_cancelled": 5, "memory_results": [], "skipped_memory_ids": []}
        manager.fos_client.delete = AsyncMock(return_value=mock_response)

        result = await manager.bulk_delete_nudges_by_memory_ids(memory_ids)

        assert result["total_cancelled"] == 5

    @pytest.mark.asyncio
    async def test_bulk_delete_nudges_empty_list(self, manager):
        result = await manager.bulk_delete_nudges_by_memory_ids([])

        assert result["total_cancelled"] == 0

    @pytest.mark.asyncio
    async def test_delete_nudges_by_user_id_success(self, manager):
        user_id = str(uuid4())
        mock_response = {"user_id": user_id, "cancelled_count": 2, "cancelled_nudge_ids": ["n1", "n2"]}
        manager.fos_client.delete = AsyncMock(return_value=mock_response)

        result = await manager.delete_nudges_by_user_id(user_id)

        assert result["cancelled_count"] == 2

    @pytest.mark.asyncio
    async def test_delete_nudges_by_user_id_empty_id(self, manager):
        with pytest.raises(ValueError, match="user_id cannot be empty"):
            await manager.delete_nudges_by_user_id("")

    @pytest.mark.asyncio
    async def test_enqueue_nudge_exception(self, manager, nudge_message):
        manager.fos_client.post = AsyncMock(side_effect=Exception("Network error"))

        with pytest.raises(Exception, match="Network error"):
            await manager.enqueue_nudge(nudge_message)

    @pytest.mark.asyncio
    async def test_get_pending_nudges_exception(self, manager):
        user_id = uuid4()
        manager.fos_client.get = AsyncMock(side_effect=Exception("Network error"))

        with pytest.raises(Exception, match="Network error"):
            await manager.get_pending_nudges(user_id)

    @pytest.mark.asyncio
    async def test_mark_processing_exception(self, manager):
        nudge_ids = [uuid4()]
        manager.fos_client.patch = AsyncMock(side_effect=Exception("Network error"))

        with pytest.raises(Exception, match="Network error"):
            await manager.mark_processing(nudge_ids)

    @pytest.mark.asyncio
    async def test_complete_nudge_exception(self, manager):
        nudge_id = uuid4()
        manager.fos_client.patch = AsyncMock(side_effect=Exception("Network error"))

        with pytest.raises(Exception, match="Network error"):
            await manager.complete_nudge(nudge_id)

    @pytest.mark.asyncio
    async def test_get_queue_stats_exception(self, manager):
        manager.fos_client.get = AsyncMock(side_effect=Exception("Network error"))

        with pytest.raises(Exception, match="Network error"):
            await manager.get_queue_stats()

    @pytest.mark.asyncio
    async def test_delete_nudges_by_memory_id_exception(self, manager):
        memory_id = "mem_123"
        manager.fos_client.delete = AsyncMock(side_effect=Exception("Network error"))

        with pytest.raises(Exception, match="Network error"):
            await manager.delete_nudges_by_memory_id(memory_id)

    @pytest.mark.asyncio
    async def test_bulk_delete_nudges_exception(self, manager):
        memory_ids = ["mem_1", "mem_2"]
        manager.fos_client.delete = AsyncMock(side_effect=Exception("Network error"))

        with pytest.raises(Exception, match="Network error"):
            await manager.bulk_delete_nudges_by_memory_ids(memory_ids)

    @pytest.mark.asyncio
    async def test_delete_nudges_by_user_id_exception(self, manager):
        user_id = str(uuid4())
        manager.fos_client.delete = AsyncMock(side_effect=Exception("Network error"))

        with pytest.raises(Exception, match="Network error"):
            await manager.delete_nudges_by_user_id(user_id)

    @pytest.mark.asyncio
    async def test_mark_processing_invalid_data(self, manager):
        nudge_ids = [uuid4()]
        invalid_nudge = {"invalid": "data"}
        mock_response = {"updated_nudges": [invalid_nudge]}
        manager.fos_client.patch = AsyncMock(return_value=mock_response)

        result = await manager.mark_processing(nudge_ids)

        assert result == []

    @pytest.mark.asyncio
    async def test_delete_nudges_by_user_id_no_response(self, manager):
        user_id = str(uuid4())
        manager.fos_client.delete = AsyncMock(return_value=None)

        result = await manager.delete_nudges_by_user_id(user_id)

        assert result["cancelled_count"] == 0

    @pytest.mark.asyncio
    async def test_bulk_delete_nudges_no_response(self, manager):
        memory_ids = ["mem_1", "mem_2"]
        manager.fos_client.delete = AsyncMock(return_value=None)

        result = await manager.bulk_delete_nudges_by_memory_ids(memory_ids)

        assert result["total_cancelled"] == 0
        assert result["skipped_memory_ids"] == memory_ids
