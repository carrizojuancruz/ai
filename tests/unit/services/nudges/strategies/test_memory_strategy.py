"""
Unit tests for app.services.nudges.strategies.memory_strategy module.

Tests cover:
- MemoryNudgeStrategy initialization
- Property access (nudge_type, requires_fos_text)
- evaluate method with various scenarios
- get_priority method
- validate_conditions method
- Error handling scenarios
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.nudges.strategies.memory_strategy import MemoryNudgeStrategy


class TestMemoryNudgeStrategyInit:
    """Test MemoryNudgeStrategy initialization."""

    @patch("app.services.nudges.strategies.memory_strategy.get_s3_vectors_store")
    def test_init_gets_s3_store(self, mock_get_store):
        """Test that constructor gets S3 vectors store."""
        mock_store = MagicMock()
        mock_get_store.return_value = mock_store

        strategy = MemoryNudgeStrategy()

        mock_get_store.assert_called_once()
        assert strategy.s3_vectors == mock_store
        assert len(strategy.memory_templates) == 4
        assert all("{memory}" in template for template in strategy.memory_templates)

    @patch("app.services.nudges.strategies.memory_strategy.get_s3_vectors_store")
    def test_init_memory_templates(self, mock_get_store):
        """Test that memory templates are properly initialized."""
        mock_get_store.return_value = MagicMock()

        strategy = MemoryNudgeStrategy()

        expected_templates = [
            "Remember this? {memory}...",
            "I was thinking about when you mentioned: {memory}",
            "This came up in my memories: {memory}",
            "Looking back at your journey: {memory}",
        ]
        assert strategy.memory_templates == expected_templates


class TestMemoryNudgeStrategyProperties:
    """Test MemoryNudgeStrategy properties."""

    @patch("app.services.nudges.strategies.memory_strategy.get_s3_vectors_store")
    def test_nudge_type_property(self, mock_get_store):
        """Test nudge_type property returns correct value."""
        mock_get_store.return_value = MagicMock()

        strategy = MemoryNudgeStrategy()

        assert strategy.nudge_type == "memory_icebreaker"

    @patch("app.services.nudges.strategies.memory_strategy.get_s3_vectors_store")
    def test_requires_fos_text_property(self, mock_get_store):
        """Test requires_fos_text property returns False."""
        mock_get_store.return_value = MagicMock()

        strategy = MemoryNudgeStrategy()

        assert strategy.requires_fos_text is False


class TestMemoryNudgeStrategyEvaluate:
    """Test MemoryNudgeStrategy.evaluate method."""

    @pytest.mark.asyncio
    @patch("app.services.nudges.strategies.memory_strategy.get_s3_vectors_store")
    @patch("app.services.nudges.strategies.memory_strategy.logger")
    async def test_evaluate_no_memory_found(self, mock_logger, mock_get_store):
        """Test evaluate returns None when no memory is found."""
        mock_store = MagicMock()
        mock_store.aget_random_recent_high_importance = AsyncMock(return_value=None)
        mock_get_store.return_value = mock_store

        strategy = MemoryNudgeStrategy()
        user_id = uuid4()
        context = {}

        result = await strategy.evaluate(user_id, context)

        assert result is None
        mock_store.aget_random_recent_high_importance.assert_called_once_with(str(user_id))
        mock_logger.debug.assert_called()

    @pytest.mark.asyncio
    @patch("app.services.nudges.strategies.memory_strategy.get_s3_vectors_store")
    @patch("app.services.nudges.strategies.memory_strategy.logger")
    async def test_evaluate_memory_found_creates_candidate(self, mock_logger, mock_get_store):
        """Test evaluate creates candidate when memory is found."""
        mock_store = MagicMock()
        memory_data = {
            "id": "mem_123",
            "summary": "This is a test memory summary that should be truncated",
            "topic_key": "test_topic",
            "importance_bin": "high"
        }
        mock_store.aget_random_recent_high_importance = AsyncMock(return_value=memory_data)
        mock_get_store.return_value = mock_store

        strategy = MemoryNudgeStrategy()
        user_id = uuid4()
        context = {}

        with patch("random.choice") as mock_random_choice:
            # Mock random choices for deterministic testing
            mock_random_choice.side_effect = [
                "Remember this? {memory}...",  # template
                "Memory from your past"        # preview
            ]

            result = await strategy.evaluate(user_id, context)

        assert result is not None
        assert result.user_id == user_id
        assert result.nudge_type == "memory_icebreaker"
        assert result.priority == 2  # high importance
        assert "This is a test memory summary" in result.notification_text
        assert result.preview_text == "Memory from your past"
        assert result.metadata["memory_id"] == "mem_123"
        assert result.metadata["memory_text"] == "This is a test memory summary that should be truncated"[:100]
        assert result.metadata["topic"] == "test_topic"
        assert result.metadata["importance"] == "high"

    @pytest.mark.asyncio
    @patch("app.services.nudges.strategies.memory_strategy.get_s3_vectors_store")
    @patch("app.services.nudges.strategies.memory_strategy.logger")
    async def test_evaluate_memory_with_empty_summary(self, mock_logger, mock_get_store):
        """Test evaluate handles memory with empty summary."""
        mock_store = MagicMock()
        memory_data = {
            "id": "mem_123",
            "summary": "",
            "topic_key": "test_topic",
            "importance_bin": "medium"
        }
        mock_store.aget_random_recent_high_importance = AsyncMock(return_value=memory_data)
        mock_get_store.return_value = mock_store

        strategy = MemoryNudgeStrategy()
        user_id = uuid4()
        context = {}

        with patch("random.choice") as mock_random_choice:
            mock_random_choice.side_effect = [
                "I was thinking about when you mentioned: {memory}",
                "Something to remember"
            ]

            result = await strategy.evaluate(user_id, context)

        assert result is not None
        assert result.priority == 1  # medium importance
        assert "I was thinking about when you mentioned:" in result.notification_text
        assert result.preview_text == "Something to remember"

    @pytest.mark.asyncio
    @patch("app.services.nudges.strategies.memory_strategy.get_s3_vectors_store")
    @patch("app.services.nudges.strategies.memory_strategy.logger")
    async def test_evaluate_memory_with_no_summary(self, mock_logger, mock_get_store):
        """Test evaluate handles memory with no summary field."""
        mock_store = MagicMock()
        memory_data = {
            "id": "mem_123",
            "topic_key": "test_topic",
            "importance_bin": "low"
        }
        mock_store.aget_random_recent_high_importance = AsyncMock(return_value=memory_data)
        mock_get_store.return_value = mock_store

        strategy = MemoryNudgeStrategy()
        user_id = uuid4()
        context = {}

        with patch("random.choice") as mock_random_choice:
            mock_random_choice.side_effect = [
                "This came up in my memories: {memory}",
                f"About {memory_data['topic_key']}"
            ]

            result = await strategy.evaluate(user_id, context)

        assert result is not None
        assert result.priority == 1  # low importance defaults to 1
        assert "This came up in my memories:" in result.notification_text
        assert result.preview_text == "About test_topic"

    @pytest.mark.asyncio
    @patch("app.services.nudges.strategies.memory_strategy.get_s3_vectors_store")
    @patch("app.services.nudges.strategies.memory_strategy.logger")
    async def test_evaluate_handles_exception(self, mock_logger, mock_get_store):
        """Test evaluate handles exceptions gracefully."""
        mock_store = MagicMock()
        mock_store.aget_random_recent_high_importance = AsyncMock(side_effect=Exception("Test error"))
        mock_get_store.return_value = mock_store

        strategy = MemoryNudgeStrategy()
        user_id = uuid4()
        context = {}

        result = await strategy.evaluate(user_id, context)

        assert result is None
        mock_logger.error.assert_called_once()


class TestMemoryNudgeStrategyGetPriority:
    """Test MemoryNudgeStrategy.get_priority method."""

    @patch("app.services.nudges.strategies.memory_strategy.get_s3_vectors_store")
    def test_get_priority_high_importance(self, mock_get_store):
        """Test get_priority returns 2 for high importance."""
        mock_get_store.return_value = MagicMock()

        strategy = MemoryNudgeStrategy()

        result = strategy.get_priority({"importance": "high"})
        assert result == 2

    @patch("app.services.nudges.strategies.memory_strategy.get_s3_vectors_store")
    def test_get_priority_medium_importance(self, mock_get_store):
        """Test get_priority returns 1 for medium importance."""
        mock_get_store.return_value = MagicMock()

        strategy = MemoryNudgeStrategy()

        result = strategy.get_priority({"importance": "medium"})
        assert result == 1

    @patch("app.services.nudges.strategies.memory_strategy.get_s3_vectors_store")
    def test_get_priority_low_importance(self, mock_get_store):
        """Test get_priority returns 1 for low importance."""
        mock_get_store.return_value = MagicMock()

        strategy = MemoryNudgeStrategy()

        result = strategy.get_priority({"importance": "low"})
        assert result == 1

    @patch("app.services.nudges.strategies.memory_strategy.get_s3_vectors_store")
    def test_get_priority_unknown_importance(self, mock_get_store):
        """Test get_priority returns 1 for unknown importance."""
        mock_get_store.return_value = MagicMock()

        strategy = MemoryNudgeStrategy()

        result = strategy.get_priority({"importance": "unknown"})
        assert result == 1

    @patch("app.services.nudges.strategies.memory_strategy.get_s3_vectors_store")
    def test_get_priority_no_importance(self, mock_get_store):
        """Test get_priority returns 1 when no importance provided."""
        mock_get_store.return_value = MagicMock()

        strategy = MemoryNudgeStrategy()

        result = strategy.get_priority({})
        assert result == 1


class TestMemoryNudgeStrategyValidateConditions:
    """Test MemoryNudgeStrategy.validate_conditions method."""

    @pytest.mark.asyncio
    @patch("app.services.nudges.strategies.memory_strategy.get_s3_vectors_store")
    async def test_validate_conditions_always_true(self, mock_get_store):
        """Test validate_conditions always returns True."""
        mock_get_store.return_value = MagicMock()

        strategy = MemoryNudgeStrategy()
        user_id = uuid4()

        result = await strategy.validate_conditions(user_id)

        assert result is True
