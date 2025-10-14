"""
Comprehensive tests for FOSHttpClient.

Tests focus on valuable business logic:
- Client initialization with and without configuration
- HTTP method implementations (GET, POST, PUT, PATCH, DELETE)
- 404 handling
- Error handling for HTTP errors and connection failures
- Header building with and without API key
- URL construction
"""
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from app.services.external_context.http_client import FOSHttpClient


class TestFOSHttpClientInitialization:
    """Test FOSHttpClient initialization."""

    def test_initialization_with_valid_config(self, mock_config):
        """Client should initialize with base URL and API key from config."""
        client = FOSHttpClient()

        assert client.base_url == "https://fos.example.com"
        assert client.api_key == "test-api-key"

    def test_initialization_strips_trailing_slash(self, mock_config):
        """Client should strip trailing slash from base URL."""
        mock_config.FOS_SERVICE_URL = "https://fos.example.com/"

        client = FOSHttpClient()

        assert client.base_url == "https://fos.example.com"

    def test_initialization_without_base_url(self, mock_config):
        """Client should handle missing base URL gracefully."""
        with patch("app.services.external_context.http_client.config") as local_cfg:
            local_cfg.FOS_SERVICE_URL = None
            local_cfg.FOS_API_KEY = "test-api-key"

            client = FOSHttpClient()

            assert client.base_url is None

    def test_initialization_without_api_key(self, mock_config):
        """Client should handle missing API key."""
        with patch("app.services.external_context.http_client.config") as local_cfg:
            local_cfg.FOS_SERVICE_URL = "https://fos.example.com"
            local_cfg.FOS_API_KEY = None

            client = FOSHttpClient()

            assert client.api_key is None


class TestBuildHeaders:
    """Test header building."""

    def test_build_headers_with_api_key(self, mock_config):
        """Should include API key in headers when configured."""
        client = FOSHttpClient()

        headers = client._build_headers()

        assert headers["Content-Type"] == "application/json"
        assert headers["x-api-key"] == "test-api-key"

    def test_build_headers_without_api_key(self, mock_config):
        """Should only include Content-Type when API key not configured."""
        with patch("app.services.external_context.http_client.config") as local_cfg:
            local_cfg.FOS_SERVICE_URL = "https://fos.example.com"
            local_cfg.FOS_API_KEY = None

            client = FOSHttpClient()
            headers = client._build_headers()

            assert headers["Content-Type"] == "application/json"
            assert "x-api-key" not in headers


class TestGet:
    """Test GET request method."""

    @pytest.mark.asyncio
    async def test_get_success(self, mock_config):
        """Should successfully make GET request and return JSON."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "value"}

        with patch("app.services.external_context.http_client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            client = FOSHttpClient()
            result = await client.get("/test-endpoint")

            assert result == {"data": "value"}
            mock_client.get.assert_called_once()
            call_args = mock_client.get.call_args
            assert call_args[0][0] == "https://fos.example.com/test-endpoint"

    @pytest.mark.asyncio
    async def test_get_with_params(self, mock_config):
        """Should include query parameters in GET request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}

        with patch("app.services.external_context.http_client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            client = FOSHttpClient()
            params = {"filter": "active", "limit": 10}
            await client.get("/users", params=params)

            call_args = mock_client.get.call_args
            assert call_args[1]["params"] == params

    @pytest.mark.asyncio
    async def test_get_returns_none_on_404(self, mock_config):
        """Should return None when endpoint returns 404."""
        mock_response = Mock()
        mock_response.status_code = 404

        with patch("app.services.external_context.http_client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            client = FOSHttpClient()
            result = await client.get("/not-found")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_returns_none_without_base_url(self, mock_config):
        """Should return None when base URL not configured."""
        mock_config.FOS_SERVICE_URL = None

        client = FOSHttpClient()
        result = await client.get("/endpoint")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_handles_http_error(self, mock_config):
        """Should return None on HTTP error status."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=Mock(), response=mock_response
        )

        with patch("app.services.external_context.http_client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            client = FOSHttpClient()
            result = await client.get("/error")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_handles_connection_error(self, mock_config):
        """Should return None on connection failure."""
        with patch("app.services.external_context.http_client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.side_effect = httpx.ConnectError("Connection failed")
            mock_client_class.return_value = mock_client

            client = FOSHttpClient()
            result = await client.get("/endpoint")

            assert result is None


class TestPost:
    """Test POST request method."""

    @pytest.mark.asyncio
    async def test_post_success(self, mock_config):
        """Should successfully make POST request with JSON data."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "123", "created": True}

        with patch("app.services.external_context.http_client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            client = FOSHttpClient()
            data = {"name": "Test", "value": 42}
            result = await client.post("/create", data)

            assert result == {"id": "123", "created": True}
            call_args = mock_client.post.call_args
            assert call_args[1]["json"] == data

    @pytest.mark.asyncio
    async def test_post_returns_none_without_base_url(self, mock_config):
        """Should return None when base URL not configured."""
        mock_config.FOS_SERVICE_URL = None

        client = FOSHttpClient()
        result = await client.post("/endpoint", {})

        assert result is None

    @pytest.mark.asyncio
    async def test_post_handles_http_error(self, mock_config):
        """Should return None on HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.reason_phrase = "Bad Request"
        mock_request = Mock()
        mock_request.url = "https://fos.example.com/error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request", request=mock_request, response=mock_response
        )

        with patch("app.services.external_context.http_client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            client = FOSHttpClient()
            result = await client.post("/error", {})

            assert result is None


class TestPut:
    """Test PUT request method."""

    @pytest.mark.asyncio
    async def test_put_success(self, mock_config):
        """Should successfully make PUT request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"updated": True}

        with patch("app.services.external_context.http_client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.put.return_value = mock_response
            mock_client_class.return_value = mock_client

            client = FOSHttpClient()
            result = await client.put("/update", {"field": "new_value"})

            assert result == {"updated": True}

    @pytest.mark.asyncio
    async def test_put_returns_none_on_404(self, mock_config):
        """Should return None when resource not found."""
        mock_response = Mock()
        mock_response.status_code = 404

        with patch("app.services.external_context.http_client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.put.return_value = mock_response
            mock_client_class.return_value = mock_client

            client = FOSHttpClient()
            result = await client.put("/not-found", {})

            assert result is None

    @pytest.mark.asyncio
    async def test_put_handles_exception(self, mock_config):
        """Should return None on exception."""
        with patch("app.services.external_context.http_client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.put.side_effect = Exception("Network error")
            mock_client_class.return_value = mock_client

            client = FOSHttpClient()
            result = await client.put("/endpoint", {})

            assert result is None


class TestPatch:
    """Test PATCH request method."""

    @pytest.mark.asyncio
    async def test_patch_success(self, mock_config):
        """Should successfully make PATCH request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"patched": True}

        with patch("app.services.external_context.http_client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.patch.return_value = mock_response
            mock_client_class.return_value = mock_client

            client = FOSHttpClient()
            result = await client.patch("/partial-update", {"status": "active"})

            assert result == {"patched": True}

    @pytest.mark.asyncio
    async def test_patch_returns_none_without_base_url(self, mock_config):
        """Should return None when base URL not configured."""
        mock_config.FOS_SERVICE_URL = None

        client = FOSHttpClient()
        result = await client.patch("/endpoint", {})

        assert result is None


class TestDelete:
    """Test DELETE request method."""

    @pytest.mark.asyncio
    async def test_delete_success(self, mock_config):
        """Should successfully make DELETE request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"deleted": True}

        with patch("app.services.external_context.http_client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.delete.return_value = mock_response
            mock_client_class.return_value = mock_client

            client = FOSHttpClient()
            result = await client.delete("/remove/123")

            assert result == {"deleted": True}

    @pytest.mark.asyncio
    async def test_delete_returns_none_without_base_url(self, mock_config):
        """Should return None when base URL not configured."""
        mock_config.FOS_SERVICE_URL = None

        client = FOSHttpClient()
        result = await client.delete("/endpoint")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_handles_exception(self, mock_config):
        """Should return None on exception."""
        with patch("app.services.external_context.http_client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.delete.side_effect = Exception("Error")
            mock_client_class.return_value = mock_client

            client = FOSHttpClient()
            result = await client.delete("/endpoint")

            assert result is None
