"""Tests for external_context/user/repository.py - ExternalUserRepository."""

from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from app.services.external_context.user.repository import ExternalUserRepository


class TestExternalUserRepository:
    """Test ExternalUserRepository CRUD operations."""

    @pytest.mark.asyncio
    @patch("app.services.external_context.user.repository.FOSHttpClient")
    async def test_get_by_id_success(self, mock_client_cls):
        """Should successfully retrieve user context by ID."""
        # Setup
        user_id = UUID("12345678-1234-5678-1234-567812345678")
        expected_data = {
            "user_id": str(user_id),
            "preferred_name": "John",
            "city": "New York"
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = expected_data
        mock_client_cls.return_value = mock_client

        # Execute
        repo = ExternalUserRepository()
        result = await repo.get_by_id(user_id)

        # Assert
        assert result == expected_data
        mock_client.get.assert_called_once_with(f"/internal/ai/context/{user_id}")

    @pytest.mark.asyncio
    @patch("app.services.external_context.user.repository.FOSHttpClient")
    async def test_get_by_id_returns_none_on_error(self, mock_client_cls):
        """Should return None when user not found or on network errors."""
        # Setup
        user_id = UUID("12345678-1234-5678-1234-567812345678")

        mock_client = AsyncMock()
        mock_client.get.return_value = None  # FOSHttpClient returns None on 404/errors
        mock_client_cls.return_value = mock_client

        # Execute
        repo = ExternalUserRepository()
        result = await repo.get_by_id(user_id)

        # Assert - graceful degradation for any error
        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.external_context.user.repository.FOSHttpClient")
    async def test_upsert_success(self, mock_client_cls):
        """Should successfully upsert user context."""
        # Setup
        user_id = UUID("12345678-1234-5678-1234-567812345678")
        context_data = {
            "preferred_name": "Jane",
            "city": "San Francisco",
            "tone_preference": "conversational"
        }
        expected_response = {"success": True, "user_id": str(user_id)}

        mock_client = AsyncMock()
        mock_client.put.return_value = expected_response
        mock_client_cls.return_value = mock_client

        # Execute
        repo = ExternalUserRepository()
        result = await repo.upsert(user_id, context_data)

        # Assert
        assert result == expected_response
        mock_client.put.assert_called_once_with(
            f"/internal/ai/context/{user_id}",
            context_data
        )

    @pytest.mark.asyncio
    @patch("app.services.external_context.user.repository.FOSHttpClient")
    async def test_upsert_failure_returns_none(self, mock_client_cls):
        """Should return None when upsert fails."""
        # Setup
        user_id = UUID("12345678-1234-5678-1234-567812345678")
        context_data = {"preferred_name": "Test"}

        mock_client = AsyncMock()
        mock_client.put.return_value = None  # API error
        mock_client_cls.return_value = mock_client

        # Execute
        repo = ExternalUserRepository()
        result = await repo.upsert(user_id, context_data)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.external_context.user.repository.FOSHttpClient")
    async def test_upsert_with_empty_data(self, mock_client_cls):
        """Should handle empty context data gracefully."""
        # Setup
        user_id = UUID("12345678-1234-5678-1234-567812345678")
        empty_data = {}

        mock_client = AsyncMock()
        mock_client.put.return_value = {"updated": False}
        mock_client_cls.return_value = mock_client

        # Execute
        repo = ExternalUserRepository()
        result = await repo.upsert(user_id, empty_data)

        # Assert - should still call API with empty data
        assert result == {"updated": False}
        mock_client.put.assert_called_once_with(
            f"/internal/ai/context/{user_id}",
            empty_data
        )

    @pytest.mark.asyncio
    @patch("app.services.external_context.user.repository.FOSHttpClient")
    async def test_repository_reuses_client_instance(self, mock_client_cls):
        """Should reuse same HTTP client for multiple operations."""
        # Setup
        user_id = UUID("12345678-1234-5678-1234-567812345678")

        mock_client = AsyncMock()
        mock_client.get.return_value = {"name": "Test"}
        mock_client.put.return_value = {"success": True}
        mock_client_cls.return_value = mock_client

        # Execute - multiple operations
        repo = ExternalUserRepository()
        await repo.get_by_id(user_id)
        await repo.upsert(user_id, {"name": "Updated"})

        # Assert - client created only once
        assert mock_client_cls.call_count == 1
