"""
Unit tests for app.services.nudges.icebreaker_processor module.

Tests cover:
- IcebreakerProcessor initialization
- get_best_icebreaker_for_user method
- process_icebreaker_for_user method
- _extract_icebreaker_text method
- Singleton factory function
- Error handling scenarios
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
from uuid import uuid4

import pytest

from app.models.nudge import NudgeRecord
from app.services.nudges.icebreaker_processor import (
    IcebreakerProcessor,
    get_icebreaker_processor,
)


def create_test_nudge(**kwargs):
    """Helper to create NudgeRecord with required default values."""
    defaults = {
        "id": uuid4(),
        "user_id": uuid4(),
        "nudge_type": "memory_icebreaker",
        "priority": 5,
        "created_at": datetime.now(),
        "status": "pending",
        "channel": "app",
        "notification_text": "",
        "preview_text": "",
    }
    defaults.update(kwargs)
    return NudgeRecord(**defaults)


class TestIcebreakerProcessorInit:
    """Test IcebreakerProcessor initialization."""

    @patch("app.services.nudges.icebreaker_processor.get_fos_nudge_manager")
    def test_init_gets_fos_manager(self, mock_get_manager):
        """Test that initialization gets FOSNudgeManager."""
        mock_manager = MagicMock()
        mock_get_manager.return_value = mock_manager

        processor = IcebreakerProcessor()

        assert processor.fos_manager is mock_manager
        mock_get_manager.assert_called_once()


class TestGetBestIcebreakerForUser:
    """Test get_best_icebreaker_for_user method."""

    @pytest.mark.asyncio
    @patch("app.services.nudges.icebreaker_processor.get_fos_nudge_manager")
    async def test_get_best_icebreaker_no_nudges(self, mock_get_manager):
        """Test when no icebreakers are available."""
        mock_manager = MagicMock()
        mock_manager.get_pending_nudges = AsyncMock(return_value=[])
        mock_get_manager.return_value = mock_manager

        processor = IcebreakerProcessor()
        user_id = uuid4()

        result = await processor.get_best_icebreaker_for_user(user_id)

        assert result is None
        mock_manager.get_pending_nudges.assert_called_once_with(
            user_id,
            nudge_type="memory_icebreaker",
            status=["pending", "processing"]
        )

    @pytest.mark.asyncio
    @patch("app.services.nudges.icebreaker_processor.get_fos_nudge_manager")
    async def test_get_best_icebreaker_single_nudge(self, mock_get_manager):
        """Test when single icebreaker is available."""
        nudge = create_test_nudge()

        mock_manager = MagicMock()
        mock_manager.get_pending_nudges = AsyncMock(return_value=[nudge])
        mock_get_manager.return_value = mock_manager

        processor = IcebreakerProcessor()
        user_id = uuid4()

        result = await processor.get_best_icebreaker_for_user(user_id)

        assert result == nudge

    @pytest.mark.asyncio
    @patch("app.services.nudges.icebreaker_processor.get_fos_nudge_manager")
    async def test_get_best_icebreaker_selects_highest_priority(self, mock_get_manager):
        """Test that highest priority icebreaker is selected."""
        now = datetime.now()
        nudge_low = create_test_nudge(priority=3, created_at=now)
        nudge_high = create_test_nudge(priority=8, created_at=now)
        nudge_medium = create_test_nudge(priority=5, created_at=now)

        mock_manager = MagicMock()
        mock_manager.get_pending_nudges = AsyncMock(
            return_value=[nudge_low, nudge_high, nudge_medium]
        )
        mock_get_manager.return_value = mock_manager

        processor = IcebreakerProcessor()
        user_id = uuid4()

        result = await processor.get_best_icebreaker_for_user(user_id)

        assert result == nudge_high

    @pytest.mark.asyncio
    @patch("app.services.nudges.icebreaker_processor.get_fos_nudge_manager")
    async def test_get_best_icebreaker_same_priority_oldest_first(self, mock_get_manager):
        """Test that with same priority, oldest is selected."""
        old_time = datetime(2024, 1, 1, 10, 0, 0)
        new_time = datetime(2024, 1, 2, 10, 0, 0)

        nudge_new = create_test_nudge(created_at=new_time)
        nudge_old = create_test_nudge(created_at=old_time)

        mock_manager = MagicMock()
        mock_manager.get_pending_nudges = AsyncMock(return_value=[nudge_new, nudge_old])
        mock_get_manager.return_value = mock_manager

        processor = IcebreakerProcessor()
        user_id = uuid4()

        result = await processor.get_best_icebreaker_for_user(user_id)

        assert result == nudge_old

    @pytest.mark.asyncio
    @patch("app.services.nudges.icebreaker_processor.get_fos_nudge_manager")
    @patch("app.services.nudges.icebreaker_processor.logger")
    async def test_get_best_icebreaker_handles_exception(self, mock_logger, mock_get_manager):
        """Test that exceptions are handled gracefully."""
        mock_manager = MagicMock()
        mock_manager.get_pending_nudges = AsyncMock(
            side_effect=Exception("Database error")
        )
        mock_get_manager.return_value = mock_manager

        processor = IcebreakerProcessor()
        user_id = uuid4()

        result = await processor.get_best_icebreaker_for_user(user_id)

        assert result is None
        mock_logger.error.assert_called_once()


class TestProcessIcebreakerForUser:
    """Test process_icebreaker_for_user method."""

    @pytest.mark.asyncio
    @patch("app.services.nudges.icebreaker_processor.get_fos_nudge_manager")
    async def test_process_icebreaker_no_best_nudge(self, mock_get_manager):
        """Test when no best nudge is found."""
        mock_manager = MagicMock()
        mock_manager.get_pending_nudges = AsyncMock(return_value=[])
        mock_get_manager.return_value = mock_manager

        processor = IcebreakerProcessor()
        user_id = uuid4()

        result = await processor.process_icebreaker_for_user(user_id)

        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.nudges.icebreaker_processor.get_fos_nudge_manager")
    async def test_process_icebreaker_success_with_notification_text(self, mock_get_manager):
        """Test successful processing with notification_text."""
        nudge = create_test_nudge(
            notification_text="Hey! Have you thought about your savings goal?"
        )

        mock_manager = MagicMock()
        mock_manager.get_pending_nudges = AsyncMock(return_value=[nudge])
        mock_manager.mark_processing = AsyncMock()
        mock_manager.complete_nudge = AsyncMock(return_value=True)
        mock_get_manager.return_value = mock_manager

        processor = IcebreakerProcessor()
        user_id = uuid4()

        result = await processor.process_icebreaker_for_user(user_id)

        assert result == "Hey! Have you thought about your savings goal?"
        mock_manager.mark_processing.assert_called_once_with([nudge.id])
        mock_manager.complete_nudge.assert_called_once_with(nudge.id)

    @pytest.mark.asyncio
    @patch("app.services.nudges.icebreaker_processor.get_fos_nudge_manager")
    async def test_process_icebreaker_with_memory_text(self, mock_get_manager):
        """Test processing with memory_text."""
        nudge = create_test_nudge(
            memory_text="You wanted to save for a vacation",
            memory_id="mem_123",
        )

        mock_manager = MagicMock()
        mock_manager.get_pending_nudges = AsyncMock(return_value=[nudge])
        mock_manager.mark_processing = AsyncMock()
        mock_manager.complete_nudge = AsyncMock(return_value=True)
        mock_get_manager.return_value = mock_manager

        processor = IcebreakerProcessor()
        user_id = uuid4()

        result = await processor.process_icebreaker_for_user(user_id)

        assert result == "Remember this? You wanted to save for a vacation"

    @pytest.mark.asyncio
    @patch("app.services.nudges.icebreaker_processor.get_fos_nudge_manager")
    async def test_process_icebreaker_with_preview_text(self, mock_get_manager):
        """Test processing with preview_text."""
        nudge = create_test_nudge(preview_text="Budget review time!")

        mock_manager = MagicMock()
        mock_manager.get_pending_nudges = AsyncMock(return_value=[nudge])
        mock_manager.mark_processing = AsyncMock()
        mock_manager.complete_nudge = AsyncMock(return_value=True)
        mock_get_manager.return_value = mock_manager

        processor = IcebreakerProcessor()
        user_id = uuid4()

        result = await processor.process_icebreaker_for_user(user_id)

        assert result == "Budget review time!"

    @pytest.mark.asyncio
    @patch("app.services.nudges.icebreaker_processor.get_fos_nudge_manager")
    async def test_process_icebreaker_no_text_extracted(self, mock_get_manager):
        """Test when no text can be extracted."""
        nudge = create_test_nudge()

        mock_manager = MagicMock()
        mock_manager.get_pending_nudges = AsyncMock(return_value=[nudge])
        mock_get_manager.return_value = mock_manager

        processor = IcebreakerProcessor()
        user_id = uuid4()

        result = await processor.process_icebreaker_for_user(user_id)

        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.nudges.icebreaker_processor.get_fos_nudge_manager")
    @patch("app.services.nudges.icebreaker_processor.logger")
    async def test_process_icebreaker_mark_processing_fails(self, mock_logger, mock_get_manager):
        """Test when mark_processing fails."""
        nudge = create_test_nudge(notification_text="Test text")

        mock_manager = MagicMock()
        mock_manager.get_pending_nudges = AsyncMock(return_value=[nudge])
        mock_manager.mark_processing = AsyncMock(side_effect=Exception("Mark failed"))
        mock_manager.complete_nudge = AsyncMock(return_value=True)
        mock_get_manager.return_value = mock_manager

        processor = IcebreakerProcessor()
        user_id = uuid4()

        result = await processor.process_icebreaker_for_user(user_id)

        # Should still return text despite mark_processing failure
        assert result == "Test text"
        mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    @patch("app.services.nudges.icebreaker_processor.get_fos_nudge_manager")
    @patch("app.services.nudges.icebreaker_processor.logger")
    async def test_process_icebreaker_complete_fails(self, mock_logger, mock_get_manager):
        """Test when complete_nudge fails."""
        nudge = create_test_nudge(notification_text="Test text")

        mock_manager = MagicMock()
        mock_manager.get_pending_nudges = AsyncMock(return_value=[nudge])
        mock_manager.mark_processing = AsyncMock()
        mock_manager.complete_nudge = AsyncMock(return_value=False)
        mock_get_manager.return_value = mock_manager

        processor = IcebreakerProcessor()
        user_id = uuid4()

        result = await processor.process_icebreaker_for_user(user_id)

        # Should still return text despite completion failure
        assert result == "Test text"
        # Warning should be logged
        assert any(
            "cleanup_failed" in str(call) for call in mock_logger.warning.call_args_list
        )

    @pytest.mark.asyncio
    @patch("app.services.nudges.icebreaker_processor.get_fos_nudge_manager")
    @patch("app.services.nudges.icebreaker_processor.logger")
    async def test_process_icebreaker_complete_raises_exception(self, mock_logger, mock_get_manager):
        """Test when complete_nudge raises exception."""
        nudge = create_test_nudge(notification_text="Test text")

        mock_manager = MagicMock()
        mock_manager.get_pending_nudges = AsyncMock(return_value=[nudge])
        mock_manager.mark_processing = AsyncMock()
        mock_manager.complete_nudge = AsyncMock(side_effect=Exception("Complete failed"))
        mock_get_manager.return_value = mock_manager

        processor = IcebreakerProcessor()
        user_id = uuid4()

        result = await processor.process_icebreaker_for_user(user_id)

        # Should still return text despite exception
        assert result == "Test text"
        mock_logger.error.assert_called()

    @pytest.mark.asyncio
    @patch("app.services.nudges.icebreaker_processor.get_fos_nudge_manager")
    @patch("app.services.nudges.icebreaker_processor.logger")
    async def test_process_icebreaker_general_exception(self, mock_logger, mock_get_manager):
        """Test general exception handling."""
        mock_manager = MagicMock()
        mock_manager.get_pending_nudges = AsyncMock(
            side_effect=Exception("Database error")
        )
        mock_get_manager.return_value = mock_manager

        processor = IcebreakerProcessor()
        user_id = uuid4()

        result = await processor.process_icebreaker_for_user(user_id)

        assert result is None
        mock_logger.error.assert_called()


class TestExtractIcebreakerText:
    """Test _extract_icebreaker_text method."""

    @patch("app.services.nudges.icebreaker_processor.get_fos_nudge_manager")
    def test_extract_notification_text(self, mock_get_manager):
        """Test extracting notification_text."""
        nudge = create_test_nudge(notification_text="  Hello!  ")

        processor = IcebreakerProcessor()
        result = processor._extract_icebreaker_text(nudge)

        assert result == "Hello!"

    @patch("app.services.nudges.icebreaker_processor.get_fos_nudge_manager")
    def test_extract_memory_text(self, mock_get_manager):
        """Test extracting memory_text."""
        nudge = create_test_nudge(
            memory_text="  Your goal  ",
            memory_id="mem_123",
        )

        processor = IcebreakerProcessor()
        result = processor._extract_icebreaker_text(nudge)

        assert result == "Remember this? Your goal"

    @patch("app.services.nudges.icebreaker_processor.get_fos_nudge_manager")
    def test_extract_preview_text(self, mock_get_manager):
        """Test extracting preview_text."""
        nudge = create_test_nudge(preview_text="  Preview text  ")

        processor = IcebreakerProcessor()
        result = processor._extract_icebreaker_text(nudge)

        assert result == "Preview text"

    @patch("app.services.nudges.icebreaker_processor.get_fos_nudge_manager")
    def test_extract_priority_notification_over_memory(self, mock_get_manager):
        """Test that notification_text has priority over memory_text."""
        nudge = create_test_nudge(
            notification_text="Notification",
            memory_text="Memory",
        )

        processor = IcebreakerProcessor()
        result = processor._extract_icebreaker_text(nudge)

        assert result == "Notification"

    @patch("app.services.nudges.icebreaker_processor.get_fos_nudge_manager")
    def test_extract_priority_memory_over_preview(self, mock_get_manager):
        """Test that memory_text has priority over preview_text."""
        nudge = create_test_nudge(
            memory_text="Memory",
            preview_text="Preview",
            memory_id="mem_123",
        )

        processor = IcebreakerProcessor()
        result = processor._extract_icebreaker_text(nudge)

        assert result == "Remember this? Memory"

    @patch("app.services.nudges.icebreaker_processor.get_fos_nudge_manager")
    def test_extract_no_text_returns_none(self, mock_get_manager):
        """Test that None is returned when no text is available."""
        nudge = create_test_nudge()

        processor = IcebreakerProcessor()
        result = processor._extract_icebreaker_text(nudge)

        assert result is None

    @patch("app.services.nudges.icebreaker_processor.get_fos_nudge_manager")
    def test_extract_empty_notification_text_falls_back(self, mock_get_manager):
        """Test that empty notification_text falls back to memory_text."""
        nudge = create_test_nudge(
            notification_text="   ",
            memory_text="Memory text",
            memory_id="mem_123",
        )

        processor = IcebreakerProcessor()
        result = processor._extract_icebreaker_text(nudge)

        assert result == "Remember this? Memory text"

    @patch("app.services.nudges.icebreaker_processor.get_fos_nudge_manager")
    @patch("app.services.nudges.icebreaker_processor.logger")
    def test_extract_handles_exception(self, mock_logger, mock_get_manager):
        """Test that exceptions during extraction are handled."""
        # Create a mock that raises on attribute access
        nudge = MagicMock()
        nudge.id = uuid4()
        type(nudge).notification_text = PropertyMock(side_effect=Exception("Error"))

        processor = IcebreakerProcessor()
        result = processor._extract_icebreaker_text(nudge)

        assert result is None
        mock_logger.error.assert_called_once()


class TestGetIcebreakerProcessor:
    """Test get_icebreaker_processor factory function."""

    def test_get_icebreaker_processor_returns_singleton(self):
        """Test that get_icebreaker_processor returns same instance."""
        # Reset global state
        import app.services.nudges.icebreaker_processor as module
        module._icebreaker_processor = None

        processor1 = get_icebreaker_processor()
        processor2 = get_icebreaker_processor()
        processor3 = get_icebreaker_processor()

        assert processor1 is processor2
        assert processor2 is processor3
        assert isinstance(processor1, IcebreakerProcessor)

    def test_get_icebreaker_processor_creates_on_first_call(self):
        """Test that processor is created on first call."""
        import app.services.nudges.icebreaker_processor as module
        module._icebreaker_processor = None

        assert module._icebreaker_processor is None

        processor = get_icebreaker_processor()

        assert module._icebreaker_processor is not None
        assert processor is module._icebreaker_processor

    def test_get_icebreaker_processor_reuses_existing(self):
        """Test that existing instance is reused."""
        import app.services.nudges.icebreaker_processor as module

        # Create an instance directly
        existing_processor = IcebreakerProcessor()
        module._icebreaker_processor = existing_processor

        # Get processor via function
        processor = get_icebreaker_processor()

        assert processor is existing_processor


class TestIcebreakerProcessorIntegration:
    """Integration tests for IcebreakerProcessor."""

    @pytest.mark.asyncio
    @patch("app.services.nudges.icebreaker_processor.get_fos_nudge_manager")
    async def test_full_workflow_with_multiple_nudges(self, mock_get_manager):
        """Test complete workflow with multiple nudges."""
        now = datetime.now()

        nudges = [
            create_test_nudge(
                priority=3,
                created_at=now,
                notification_text="Low priority",
            ),
            create_test_nudge(
                priority=10,
                created_at=now,
                notification_text="High priority icebreaker",
            ),
            create_test_nudge(
                priority=5,
                created_at=now,
                notification_text="Medium priority",
            ),
        ]

        mock_manager = MagicMock()
        mock_manager.get_pending_nudges = AsyncMock(return_value=nudges)
        mock_manager.mark_processing = AsyncMock()
        mock_manager.complete_nudge = AsyncMock(return_value=True)
        mock_get_manager.return_value = mock_manager

        processor = IcebreakerProcessor()
        user_id = uuid4()

        result = await processor.process_icebreaker_for_user(user_id)

        # Should select highest priority
        assert result == "High priority icebreaker"
        # Should mark processing and complete once (but can't check specific ID due to mocking)
        mock_manager.mark_processing.assert_called_once()
        mock_manager.complete_nudge.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.nudges.icebreaker_processor.get_fos_nudge_manager")
    async def test_text_extraction_fallback_chain(self, mock_get_manager):
        """Test that text extraction follows fallback chain."""
        # Test all three text sources
        test_cases = [
            {
                "notification_text": "Notification",
                "memory_text": "Memory",
                "preview_text": "Preview",
                "expected": "Notification",
            },
            {
                "memory_text": "Memory",
                "preview_text": "Preview",
                "memory_id": "mem_123",
                "expected": "Remember this? Memory",
            },
            {
                "preview_text": "Preview",
                "expected": "Preview",
            },
        ]

        for case in test_cases:
            nudge = create_test_nudge(
                **{k: v for k, v in case.items() if k != "expected"}
            )

            mock_manager = MagicMock()
            mock_manager.get_pending_nudges = AsyncMock(return_value=[nudge])
            mock_manager.mark_processing = AsyncMock()
            mock_manager.complete_nudge = AsyncMock(return_value=True)
            mock_get_manager.return_value = mock_manager

            processor = IcebreakerProcessor()
            user_id = uuid4()

            result = await processor.process_icebreaker_for_user(user_id)

            assert result == case["expected"]
