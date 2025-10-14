"""
Unit tests for app.services.langfuse.http_client module.

Tests cover:
- LangfuseHttpClient initialization
- HTTP client creation and reuse
- get_traces method with successful responses
- get_traces method with HTTP errors
- get_traces method with request exceptions
- close method functionality
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.langfuse.http_client import LangfuseHttpClient


class TestLangfuseHttpClient:
    """Test LangfuseHttpClient class."""

    def test_init(self):
        """Test initialization with credentials and base URL."""
        public_key = "test_public_key"
        secret_key = "test_secret_key"
        base_url = "https://api.langfuse.com"

        client = LangfuseHttpClient(public_key, secret_key, base_url)

        assert client.public_key == public_key
        assert client.secret_key == secret_key
        assert client.base_url == base_url
        assert client._client is None

    @pytest.mark.asyncio
    async def test_get_client_creates_new_client(self):
        """Test _get_client creates new AsyncClient when none exists."""
        client = LangfuseHttpClient("pk", "sk", "https://api.langfuse.com")

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_client_instance = MagicMock()
            mock_async_client.return_value = mock_client_instance

            result = await client._get_client()

            assert result == mock_client_instance
            mock_async_client.assert_called_once_with(
                auth=("pk", "sk"),
                timeout=30
            )
            assert client._client == mock_client_instance

    @pytest.mark.asyncio
    async def test_get_client_reuses_existing_client(self):
        """Test _get_client reuses existing client."""
        client = LangfuseHttpClient("pk", "sk", "https://api.langfuse.com")
        existing_client = MagicMock()
        client._client = existing_client

        result = await client._get_client()

        assert result == existing_client

    @pytest.mark.asyncio
    async def test_get_traces_successful_response(self):
        """Test get_traces with successful API response."""
        client = LangfuseHttpClient("pk", "sk", "https://api.langfuse.com")
        start_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 2, tzinfo=timezone.utc)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"trace_id": "123"}]}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch.object(client, "_get_client", return_value=mock_client):
            result = await client.get_traces(start_time, end_time)

            assert result == [{"trace_id": "123"}]
            mock_client.get.assert_called_once_with(
                "https://api.langfuse.com/api/public/traces",
                params={
                    "fromTimestamp": "2024-01-01T00:00:00+00:00Z",
                    "toTimestamp": "2024-01-02T00:00:00+00:00Z",
                    "limit": 100
                }
            )

    @pytest.mark.asyncio
    async def test_get_traces_http_error_response(self):
        """Test get_traces with HTTP error response."""
        client = LangfuseHttpClient("pk", "sk", "https://api.langfuse.com")
        start_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 2, tzinfo=timezone.utc)

        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch.object(client, "_get_client", return_value=mock_client), \
             patch("app.services.langfuse.http_client.logger") as mock_logger:

            result = await client.get_traces(start_time, end_time)

            assert result == []
            mock_logger.warning.assert_called_once_with(
                "Langfuse API returned status 500"
            )

    @pytest.mark.asyncio
    async def test_get_traces_request_error(self):
        """Test get_traces with httpx.RequestError."""
        import httpx

        client = LangfuseHttpClient("pk", "sk", "https://api.langfuse.com")
        start_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 2, tzinfo=timezone.utc)

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.RequestError("Connection failed")

        with patch.object(client, "_get_client", return_value=mock_client), \
             patch("app.services.langfuse.http_client.logger") as mock_logger:

            result = await client.get_traces(start_time, end_time)

            assert result == []
            mock_logger.error.assert_called_once_with(
                "HTTP request failed: Connection failed"
            )

    @pytest.mark.asyncio
    async def test_get_traces_unexpected_error(self):
        """Test get_traces with unexpected exception."""
        client = LangfuseHttpClient("pk", "sk", "https://api.langfuse.com")
        start_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 2, tzinfo=timezone.utc)

        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Unexpected error")

        with patch.object(client, "_get_client", return_value=mock_client), \
             patch("app.services.langfuse.http_client.logger") as mock_logger:

            result = await client.get_traces(start_time, end_time)

            assert result == []
            mock_logger.error.assert_called_once_with(
                "Unexpected error fetching traces: Unexpected error"
            )

    @pytest.mark.asyncio
    async def test_close_with_existing_client(self):
        """Test close method with existing client."""
        client = LangfuseHttpClient("pk", "sk", "https://api.langfuse.com")
        mock_client = AsyncMock()
        client._client = mock_client

        await client.close()

        mock_client.aclose.assert_called_once()
        assert client._client is None

    @pytest.mark.asyncio
    async def test_close_without_client(self):
        """Test close method when no client exists."""
        client = LangfuseHttpClient("pk", "sk", "https://api.langfuse.com")
        client._client = None

        await client.close()

        # Should not raise any exception
        assert client._client is None
