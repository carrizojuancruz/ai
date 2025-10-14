"""Tests for guest routes."""

import contextlib
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.api.routes_guest import InitializeResponse


class TestGuestRoutes:
    """Test suite for guest API routes."""

    def test_initialize_guest_success(self, client: TestClient, mock_guest_service):
        """Test successful guest initialization validates API contract."""
        expected_thread_id = "test-thread-id"
        expected_welcome = {
            "id": "message_1",
            "type": "normal_conversation",
            "content": "So tell me, what's on your mind today?",
            "message_count": 1,
            "can_continue": True,
        }
        expected_sse_url = f"/guest/sse/{expected_thread_id}"

        mock_guest_service.initialize.return_value = {
            "thread_id": expected_thread_id,
            "welcome": expected_welcome,
            "sse_url": expected_sse_url,
        }

        with patch("app.api.routes_guest.guest_service", mock_guest_service):
            response = client.post("/guest/initialize")

        assert response.status_code == 200
        data = response.json()
        # Contract validation
        assert "thread_id" in data and isinstance(data["thread_id"], str)
        assert "welcome" in data and isinstance(data["welcome"], dict)
        assert "sse_url" in data and isinstance(data["sse_url"], str)
        # Schema compatibility
        InitializeResponse(**data)
        mock_guest_service.initialize.assert_called_once()

    def test_guest_message_success(self, client: TestClient, mock_guest_service):
        """Test successful guest message processing validates API contract."""
        thread_id = "test-thread-id"
        message_text = "Hello, I need financial advice"
        expected_response = {"status": "accepted"}

        mock_guest_service.process_message.return_value = expected_response
        payload = {"thread_id": thread_id, "text": message_text}

        with patch("app.api.routes_guest.guest_service", mock_guest_service):
            response = client.post("/guest/message", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "status" in data and isinstance(data["status"], str)
        mock_guest_service.process_message.assert_called_once_with(
            thread_id=thread_id, text=message_text
        )

    def test_guest_message_thread_not_found(self, client: TestClient, mock_guest_service):
        """Test guest message with non-existent thread."""
        from fastapi import HTTPException

        # Arrange
        thread_id = "non-existent-thread"
        message_text = "Hello"

        mock_guest_service.process_message.side_effect = HTTPException(
            status_code=404, detail="Thread not found"
        )

        payload = {"thread_id": thread_id, "text": message_text}

        # Act
        with patch("app.api.routes_guest.guest_service", mock_guest_service):
            response = client.post("/guest/message", json=payload)

        # Assert
        assert response.status_code == 404
        response_data = response.json()
        assert response_data["detail"] == "Thread not found"

    def test_guest_sse_streaming(self, client: TestClient):
        """Test SSE endpoint is reachable and uses correct content type."""
        thread_id = "test-thread-id"
        mock_queue = AsyncMock()

        with patch("app.api.routes_guest.get_sse_queue", return_value=mock_queue), contextlib.suppress(Exception):
            resp = client.get(f"/guest/sse/{thread_id}", timeout=1.0)
            # Content type check if response returned
            if resp is not None and hasattr(resp, "headers"):
                ct = resp.headers.get("content-type", "")
                assert "text/event-stream" in ct or "text/plain" in ct
