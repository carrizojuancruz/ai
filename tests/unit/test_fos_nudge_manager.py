"""Unit tests for FOSNudgeManager service."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.models.nudge import NudgeChannel, NudgeRecord
from app.services.nudges.fos_manager import FOSNudgeManager, FOSNudgeStats
from app.services.nudges.models import NudgeMessage


class TestFOSNudgeManager:
    """Test FOSNudgeManager service class."""

    @pytest.fixture
    def fos_manager(self):
        """Create FOSNudgeManager instance for testing."""
        with patch('app.services.nudges.fos_manager.FOSHttpClient') as mock_client:
            manager = FOSNudgeManager()
            manager.fos_client = mock_client.return_value
            return manager

    @pytest.fixture
    def sample_nudge_message(self):
        """Create sample nudge message for testing."""
        return NudgeMessage(
            user_id=uuid4(),
            nudge_type="memory_icebreaker",
            priority=5,
            payload={"test": "data"},
            channel=NudgeChannel.APP
        )

    @pytest.fixture
    def sample_nudge_record(self):
        """Create sample nudge record for testing."""
        return NudgeRecord(
            id=uuid4(),
            user_id=uuid4(),
            nudge_type="memory_icebreaker",
            content="Test nudge content",
            metadata={"test": "data"},
            priority=5,
            status="pending",
            channel="app",
            created_at="2023-01-01T00:00:00Z",
            updated_at="2023-01-01T00:00:00Z"
        )

    @pytest.mark.asyncio
    async def test_enqueue_nudge_success(self, fos_manager, sample_nudge_message):
        """Test successful nudge enqueuing."""
        # Mock successful response
        mock_response = {"message_id": "test-message-id"}
        fos_manager.fos_client.post = AsyncMock(return_value=mock_response)

        # Call the method
        result = await fos_manager.enqueue_nudge(sample_nudge_message)

        # Verify result
        assert result == "test-message-id"

        # Verify API call
        fos_manager.fos_client.post.assert_called_once_with(
            "/api/nudges",
            {
                "user_id": str(sample_nudge_message.user_id),
                "nudge_type": "memory_icebreaker",
                "payload": {"test": "data"},
                "priority": 5,
                "channel": NudgeChannel.APP
            }
        )

    @pytest.mark.asyncio
    async def test_enqueue_nudge_no_response(self, fos_manager, sample_nudge_message):
        """Test nudge enqueuing with no response from FOS service."""
        # Mock no response
        fos_manager.fos_client.post = AsyncMock(return_value=None)

        # Call the method and expect exception
        with pytest.raises(Exception, match="FOS service request failed - no response"):
            await fos_manager.enqueue_nudge(sample_nudge_message)

    @pytest.mark.asyncio
    async def test_enqueue_nudge_no_message_id(self, fos_manager, sample_nudge_message):
        """Test nudge enqueuing with response missing message_id."""
        # Mock response without message_id
        mock_response = {"status": "queued"}
        fos_manager.fos_client.post = AsyncMock(return_value=mock_response)

        # Call the method and expect exception
        with pytest.raises(ValueError, match="FOS service did not return message_id"):
            await fos_manager.enqueue_nudge(sample_nudge_message)

    @pytest.mark.asyncio
    async def test_get_pending_nudges_success(self, fos_manager):
        """Test successful retrieval of pending nudges."""
        user_id = uuid4()
        nudge_id = uuid4()

        # Mock successful response
        mock_response = {
            "nudges": [
                {
                    "id": str(nudge_id),
                    "user_id": str(user_id),
                    "nudge_type": "memory_icebreaker",
                    "notification_text": "Test notification",
                    "preview_text": "Test preview",
                    "priority": 5,
                    "status": "pending",
                    "channel": "app",
                    "created_at": "2023-01-01T00:00:00Z",
                    "updated_at": "2023-01-01T00:00:00Z",
                    "metadata": {"test": "data"}
                }
            ]
        }
        fos_manager.fos_client.get = AsyncMock(return_value=mock_response)

        # Call the method
        result = await fos_manager.get_pending_nudges(user_id)

        # Verify result
        assert len(result) == 1
        assert result[0].id == nudge_id
        assert result[0].user_id == user_id
        assert result[0].nudge_type == "memory_icebreaker"
        assert result[0].status == "pending"

        # Verify API call
        fos_manager.fos_client.get.assert_called_once_with(
            f"/api/nudges?user_id={user_id}&status=pending"
        )

    @pytest.mark.asyncio
    async def test_get_pending_nudges_no_response(self, fos_manager):
        """Test retrieval of pending nudges with no response."""
        user_id = uuid4()
        fos_manager.fos_client.get = AsyncMock(return_value=None)

        # Call the method
        result = await fos_manager.get_pending_nudges(user_id)

        # Verify empty result
        assert result == []

    @pytest.mark.asyncio
    async def test_get_pending_nudges_invalid_data(self, fos_manager):
        """Test handling of invalid nudge data."""
        user_id = uuid4()

        # Mock response with invalid data
        mock_response = {
            "nudges": [
                {
                    "id": "invalid-uuid",  # Invalid UUID
                    "user_id": str(user_id),
                    "nudge_type": "memory_icebreaker"
                    # Missing required fields
                },
                {
                    "id": str(uuid4()),
                    "user_id": str(user_id),
                    "nudge_type": "valid_nudge",
                    "notification_text": "Valid notification",
                    "preview_text": "Valid preview",
                    "priority": 5,
                    "status": "pending",
                    "channel": "app",
                    "created_at": "2023-01-01T00:00:00Z",
                    "metadata": {"test": "data"}
                }
            ]
        }
        fos_manager.fos_client.get = AsyncMock(return_value=mock_response)

        # Call the method
        result = await fos_manager.get_pending_nudges(user_id)

        # Verify only valid nudge is returned
        assert len(result) == 1
        assert result[0].nudge_type == "valid_nudge"

    @pytest.mark.asyncio
    async def test_mark_processing_success(self, fos_manager):
        """Test successful marking of nudges as processing."""
        nudge_ids = [uuid4(), uuid4()]

        # Mock successful response
        mock_response = {
            "updated_nudges": [
                {
                    "id": str(nudge_ids[0]),
                    "user_id": str(uuid4()),
                    "nudge_type": "test_nudge",
                    "notification_text": "Test notification",
                    "preview_text": "Test preview",
                    "priority": 5,
                    "status": "processing",
                    "channel": "app",
                    "created_at": "2023-01-01T00:00:00Z",
                    "metadata": {"test": "data"}
                }
            ]
        }
        fos_manager.fos_client.put = AsyncMock(return_value=mock_response)

        # Call the method
        result = await fos_manager.mark_processing(nudge_ids)

        # Verify result
        assert len(result) == 1
        assert result[0].id == nudge_ids[0]
        assert result[0].status == "processing"

        # Verify API call
        fos_manager.fos_client.put.assert_called_once_with(
            "/api/nudges/status",
            {
                "nudge_ids": [str(nid) for nid in nudge_ids],
                "status": "processing"
            }
        )

    @pytest.mark.asyncio
    async def test_complete_nudge_success(self, fos_manager):
        """Test successful nudge completion."""
        nudge_id = uuid4()

        # Mock successful response
        mock_response = {"updated_count": 1}
        fos_manager.fos_client.put = AsyncMock(return_value=mock_response)

        # Call the method
        result = await fos_manager.complete_nudge(nudge_id)

        # Verify result
        assert result is True

        # Verify API call
        fos_manager.fos_client.put.assert_called_once_with(
            "/api/nudges/status",
            {
                "nudge_ids": [str(nudge_id)],
                "status": "sent"
            }
        )

    @pytest.mark.asyncio
    async def test_complete_nudge_failure(self, fos_manager):
        """Test nudge completion failure."""
        nudge_id = uuid4()

        # Mock failure response
        mock_response = {"updated_count": 0}
        fos_manager.fos_client.put = AsyncMock(return_value=mock_response)

        # Call the method
        result = await fos_manager.complete_nudge(nudge_id)

        # Verify result
        assert result is False

    @pytest.mark.asyncio
    async def test_complete_nudge_no_response(self, fos_manager):
        """Test nudge completion with no response."""
        nudge_id = uuid4()
        fos_manager.fos_client.put = AsyncMock(return_value=None)

        # Call the method
        result = await fos_manager.complete_nudge(nudge_id)

        # Verify result
        assert result is False

    @pytest.mark.asyncio
    async def test_get_queue_stats_success(self, fos_manager):
        """Test successful queue stats retrieval."""
        # Mock successful response
        mock_response = {
            "pending_count": 10,
            "processing_count": 5,
            "total_count": 15
        }
        fos_manager.fos_client.get = AsyncMock(return_value=mock_response)

        # Call the method
        result = await fos_manager.get_queue_stats()

        # Verify result
        assert isinstance(result, FOSNudgeStats)
        assert result.pending_count == 10
        assert result.processing_count == 5
        assert result.total_count == 15

        # Verify API call
        fos_manager.fos_client.get.assert_called_once_with("/api/nudges/stats")

    @pytest.mark.asyncio
    async def test_get_queue_stats_with_user_filter(self, fos_manager):
        """Test queue stats retrieval with user filter."""
        user_id = uuid4()
        mock_response = {"pending_count": 3, "processing_count": 1, "total_count": 4}
        fos_manager.fos_client.get = AsyncMock(return_value=mock_response)

        # Call the method
        result = await fos_manager.get_queue_stats(user_id)

        # Verify result
        assert result.pending_count == 3

        # Verify API call with user filter
        fos_manager.fos_client.get.assert_called_once_with(f"/api/nudges/stats?user_id={user_id}")

    @pytest.mark.asyncio
    async def test_get_queue_stats_no_response(self, fos_manager):
        """Test queue stats retrieval with no response."""
        fos_manager.fos_client.get = AsyncMock(return_value=None)

        # Call the method
        result = await fos_manager.get_queue_stats()

        # Verify default stats
        assert result.pending_count == 0
        assert result.processing_count == 0
        assert result.total_count == 0

    @pytest.mark.asyncio
    async def test_health_check_success(self, fos_manager):
        """Test successful health check."""
        # Mock healthy response
        mock_response = {"status": "ok"}
        fos_manager.fos_client.get = AsyncMock(return_value=mock_response)

        # Call the method
        result = await fos_manager.health_check()

        # Verify result
        assert result is True

        # Verify API call
        fos_manager.fos_client.get.assert_called_once_with("/api/health")

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, fos_manager):
        """Test health check with unhealthy response."""
        # Mock unhealthy response
        mock_response = {"status": "error"}
        fos_manager.fos_client.get = AsyncMock(return_value=mock_response)

        # Call the method
        result = await fos_manager.health_check()

        # Verify result
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_no_response(self, fos_manager):
        """Test health check with no response."""
        fos_manager.fos_client.get = AsyncMock(return_value=None)

        # Call the method
        result = await fos_manager.health_check()

        # Verify result
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_exception(self, fos_manager):
        """Test health check with exception."""
        fos_manager.fos_client.get = AsyncMock(side_effect=Exception("Connection failed"))

        # Call the method
        result = await fos_manager.health_check()

        # Verify result
        assert result is False
