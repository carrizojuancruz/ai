"""
Comprehensive tests for service utilities.

Tests focus on valuable business logic:
- Blocked topics retrieval from external service
- Response format handling (list vs dict)
- Error handling and fallbacks
- Empty response handling
"""
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.services.utils import get_blocked_topics


class TestGetBlockedTopics:
    """Test blocked topics retrieval from external service."""

    @pytest.mark.asyncio
    async def test_retrieves_and_parses_blocked_topics(self):
        """Should successfully retrieve blocked topics from external service."""
        mock_response = [
            {"topic": "politics"},
            {"topic": "religion"},
            {"topic": "controversial"}
        ]

        with patch("app.services.utils.FOSHttpClient") as mock_client_class:
            mock_client = Mock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await get_blocked_topics("user123")

            assert result == ["politics", "religion", "controversial"]
            mock_client.get.assert_called_once_with(
                endpoint="/internal/users/blocked_topics/user123"
            )

    @pytest.mark.asyncio
    async def test_handles_empty_and_none_responses(self):
        """Should return empty list for None or empty list responses."""
        with patch("app.services.utils.FOSHttpClient") as mock_client_class:
            mock_client = Mock()

            # Test None response
            mock_client.get = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            result = await get_blocked_topics("user123")
            assert result == []

            # Test empty list response
            mock_client.get = AsyncMock(return_value=[])
            result = await get_blocked_topics("user123")
            assert result == []

    @pytest.mark.asyncio
    async def test_filters_items_without_topic_field(self):
        """Should filter out items missing or with empty topic field."""
        mock_response = [
            {"topic": "valid1"},
            {},
            {"topic": ""},
            {"topic": "valid2"},
            {"other": "field"}
        ]

        with patch("app.services.utils.FOSHttpClient") as mock_client_class:
            mock_client = Mock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await get_blocked_topics("user123")

            assert result == ["valid1", "valid2"]

    @pytest.mark.asyncio
    async def test_handles_non_list_response(self):
        """Should return empty list for non-list responses."""
        with patch("app.services.utils.FOSHttpClient") as mock_client_class:
            mock_client = Mock()
            mock_client.get = AsyncMock(return_value={"error": "invalid"})
            mock_client_class.return_value = mock_client

            result = await get_blocked_topics("user123")

            assert result == []
