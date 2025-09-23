"""Unit tests for DatabaseNudgeManager service - corrected version."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from app.models.nudge import NudgeChannel, NudgeRecord, NudgeStatus
from app.services.nudges.database_manager import DatabaseNudgeManager
from app.services.queue.sqs_manager import NudgeMessage


class TestDatabaseNudgeManager:
    """Test DatabaseNudgeManager service class with correct interface."""

    @pytest.fixture
    def mock_db_service(self):
        """Create mock database service."""
        db_service = Mock()
        
        # Create a mock session that properly implements async context manager
        mock_session = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        
        db_service.get_session = AsyncMock(return_value=mock_context_manager)
        
        # Mock repository
        mock_repo = Mock()
        mock_repo.create_nudge = AsyncMock()
        mock_repo.get_user_nudges = AsyncMock()
        mock_repo.mark_processing = AsyncMock()
        mock_repo.update_status = AsyncMock()
        mock_repo.delete_by_ids = AsyncMock()
        
        db_service.get_nudge_repository = Mock(return_value=mock_repo)
        
        return db_service, mock_repo

    @pytest.fixture
    def nudge_manager(self, mock_db_service):
        """Create DatabaseNudgeManager instance with mock database service."""
        db_service, _ = mock_db_service
        with patch('app.services.nudges.database_manager.get_database_service', return_value=db_service):
            return DatabaseNudgeManager()

    @pytest.fixture
    def sample_nudge_message(self):
        """Sample NudgeMessage for testing."""
        return NudgeMessage(
            user_id=uuid4(),
            nudge_type="market_update",
            priority=5,
            channel="email",  # Use lowercase enum value
            payload={
                "notification_text": "Market update available",
                "preview_text": "Check out the latest market trends",
                "metadata": {"source": "portfolio_tracker"}
            }
        )

    @pytest.fixture
    def sample_nudge_record(self):
        """Sample NudgeRecord for testing."""
        return NudgeRecord(
            id=uuid4(),
            user_id=uuid4(),
            nudge_type="market_update",
            priority=5,
            status=NudgeStatus.PENDING,
            channel=NudgeChannel.EMAIL,
            notification_text="Market update available",
            preview_text="Check out the latest market trends",
            created_at=datetime.now()
        )

    @pytest.mark.asyncio
    async def test_enqueue_nudge_success(self, nudge_manager, mock_db_service, sample_nudge_message, sample_nudge_record):
        """Test successful nudge enqueueing."""
        _, mock_repo = mock_db_service
        mock_repo.create_nudge.return_value = sample_nudge_record

        result = await nudge_manager.enqueue_nudge(sample_nudge_message)

        assert result == str(sample_nudge_record.id)
        mock_repo.create_nudge.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_pending_nudges_success(self, nudge_manager, mock_db_service, sample_nudge_record):
        """Test retrieving pending nudges for a user."""
        _, mock_repo = mock_db_service
        user_id = uuid4()
        mock_repo.get_user_nudges.return_value = [sample_nudge_record]

        result = await nudge_manager.get_pending_nudges(user_id, limit=10)

        assert len(result) == 1
        assert result[0] == sample_nudge_record
        mock_repo.get_user_nudges.assert_called_once_with(
            user_id=user_id,
            status=NudgeStatus.PENDING,
            limit=10
        )

    @pytest.mark.asyncio
    async def test_get_pending_nudges_empty_result(self, nudge_manager, mock_db_service):
        """Test retrieving pending nudges when none exist."""
        _, mock_repo = mock_db_service
        user_id = uuid4()
        mock_repo.get_user_nudges.return_value = []

        result = await nudge_manager.get_pending_nudges(user_id, limit=10)

        assert result == []

    @pytest.mark.asyncio
    async def test_mark_processing_success(self, nudge_manager, mock_db_service, sample_nudge_record):
        """Test marking nudges as processing."""
        _, mock_repo = mock_db_service
        nudge_ids = [uuid4(), uuid4()]
        mock_repo.mark_processing.return_value = [sample_nudge_record]

        result = await nudge_manager.mark_processing(nudge_ids)

        assert result == [sample_nudge_record]
        mock_repo.mark_processing.assert_called_once_with(nudge_ids)

    @pytest.mark.asyncio
    async def test_mark_processing_failure(self, nudge_manager, mock_db_service):
        """Test marking nudges as processing when it fails."""
        _, mock_repo = mock_db_service
        nudge_ids = [uuid4()]
        mock_repo.mark_processing.side_effect = Exception("Database error")

        result = await nudge_manager.mark_processing(nudge_ids)

        assert result == []

    @pytest.mark.asyncio
    async def test_complete_nudge_success(self, nudge_manager, mock_db_service, sample_nudge_record):
        """Test completing a nudge successfully."""
        _, mock_repo = mock_db_service
        nudge_id = uuid4()
        mock_repo.update_status.return_value = sample_nudge_record

        result = await nudge_manager.complete_nudge(nudge_id)

        assert result is True
        mock_repo.update_status.assert_called_once_with(
            nudge_id=nudge_id,
            status=NudgeStatus.PROCESSED,
            processed_at=True
        )

    @pytest.mark.asyncio
    async def test_complete_nudge_not_found(self, nudge_manager, mock_db_service):
        """Test completing a nudge that doesn't exist."""
        _, mock_repo = mock_db_service
        nudge_id = uuid4()
        mock_repo.update_status.return_value = None

        result = await nudge_manager.complete_nudge(nudge_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_nudges_success(self, nudge_manager, mock_db_service):
        """Test deleting nudges successfully."""
        _, mock_repo = mock_db_service
        nudge_ids = [uuid4(), uuid4(), uuid4()]
        mock_repo.delete_by_ids.return_value = len(nudge_ids)

        result = await nudge_manager.delete_nudges(nudge_ids)

        assert result == 3
        mock_repo.delete_by_ids.assert_called_once_with(nudge_ids)

    @pytest.mark.asyncio
    async def test_delete_nudges_failure(self, nudge_manager, mock_db_service):
        """Test deleting nudges when it fails."""
        _, mock_repo = mock_db_service
        nudge_ids = [uuid4()]
        mock_repo.delete_by_ids.side_effect = Exception("Database error")

        result = await nudge_manager.delete_nudges(nudge_ids)

        assert result == 0

    def test_nudge_manager_interface_compliance(self, nudge_manager):
        """Test that DatabaseNudgeManager has required interface methods."""
        required_methods = [
            "enqueue_nudge",
            "get_pending_nudges",
            "mark_processing",
            "complete_nudge",
            "delete_nudges",
            "is_latest_nudge"
        ]
        
        for method in required_methods:
            assert hasattr(nudge_manager, method), f"Missing method: {method}"
            assert callable(getattr(nudge_manager, method)), f"Method not callable: {method}"

    def test_nudge_manager_initialization(self):
        """Test DatabaseNudgeManager initialization."""
        with patch('app.services.nudges.database_manager.get_database_service'):
            manager = DatabaseNudgeManager()
            
            assert hasattr(manager, 'db_service')
            assert hasattr(manager, '_in_flight_messages')
            assert isinstance(manager._in_flight_messages, dict)

    @pytest.mark.asyncio
    async def test_is_latest_nudge_no_previous(self, nudge_manager):
        """Test is_latest_nudge when no previous nudge exists."""
        result = await nudge_manager.is_latest_nudge("user123", "market_update", "2024-01-01T10:00:00")

        assert result is True

    @pytest.mark.asyncio
    async def test_is_latest_nudge_with_newer_timestamp(self, nudge_manager):
        """Test is_latest_nudge with newer timestamp."""
        # Set up an older timestamp in memory
        nudge_manager._in_flight_messages["user123:market_update"] = datetime.fromisoformat("2024-01-01T09:00:00")

        result = await nudge_manager.is_latest_nudge("user123", "market_update", "2024-01-01T10:00:00")

        assert result is True

    @pytest.mark.asyncio
    async def test_is_latest_nudge_with_older_timestamp(self, nudge_manager):
        """Test is_latest_nudge with older timestamp."""
        # Set up a newer timestamp in memory
        nudge_manager._in_flight_messages["user123:market_update"] = datetime.fromisoformat("2024-01-01T11:00:00")

        result = await nudge_manager.is_latest_nudge("user123", "market_update", "2024-01-01T10:00:00")

        assert result is False

