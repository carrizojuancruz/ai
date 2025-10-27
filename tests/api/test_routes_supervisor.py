"""Tests for supervisor routes."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


class TestSupervisorRoutes:
    """Test suite for supervisor API routes."""

    @pytest.mark.parametrize(
        "has_prior_summary",
        [True, False],
    )
    def test_initialize_supervisor_success(
        self, client: TestClient, mock_supervisor_service, has_prior_summary
    ):
        """Test successful supervisor initialization validates API contract."""
        user_id = uuid4()
        expected_thread_id = "test-supervisor-thread-id"
        expected_welcome = "Welcome! How can I help you today?"
        expected_sse_url = f"/supervisor/sse/{expected_thread_id}"
        expected_prior_summary = "Previous conversation about budgeting" if has_prior_summary else None

        mock_supervisor_service.initialize.return_value = {
            "thread_id": expected_thread_id,
            "welcome": expected_welcome,
            "sse_url": expected_sse_url,
            "prior_conversation_summary": expected_prior_summary,
        }

        payload = {"user_id": str(user_id)}

        with patch("app.api.routes_supervisor.supervisor_service", mock_supervisor_service):
            response = client.post("/supervisor/initialize", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "thread_id" in data and isinstance(data["thread_id"], str)
        assert "welcome" in data and isinstance(data["welcome"], str)
        assert "sse_url" in data and isinstance(data["sse_url"], str)
        assert "prior_conversation_summary" in data and (
            isinstance(data["prior_conversation_summary"], str)
            or data["prior_conversation_summary"] is None
        )

        mock_supervisor_service.initialize.assert_called_once()
        call_kwargs = mock_supervisor_service.initialize.call_args[1]
        assert call_kwargs["user_id"] == user_id

    @pytest.mark.parametrize(
        "scenario,expected_status,expected_detail",
        [
            ("success", 200, None),
            ("empty_text", 400, "Message text must not be empty"),
            ("whitespace_text", 400, "Message text must not be empty"),
            ("missing_thread_id", 422, None),
            ("missing_text", 422, None),
        ],
    )
    def test_supervisor_message(
        self, client: TestClient, mock_supervisor_service, scenario, expected_status, expected_detail
    ):
        """Test supervisor message processing with various scenarios."""
        thread_id = "test-supervisor-thread-id"

        if scenario == "success":
            message_text = "I need help with retirement planning"
            mock_supervisor_service.process_message.return_value = None
            payload = {"thread_id": thread_id, "text": message_text}

            with patch("app.api.routes_supervisor.supervisor_service", mock_supervisor_service):
                response = client.post("/supervisor/message", json=payload)

            assert response.status_code == 200
            data = response.json()
            assert "status" in data and isinstance(data["status"], str)
            mock_supervisor_service.process_message.assert_called_once_with(
                thread_id=thread_id, text=message_text, voice=True
            )
        elif scenario == "empty_text":
            payload = {"thread_id": thread_id, "text": ""}
            with patch("app.api.routes_supervisor.supervisor_service", mock_supervisor_service):
                response = client.post("/supervisor/message", json=payload)
            assert response.status_code == expected_status
            assert response.json()["detail"] == expected_detail
            mock_supervisor_service.process_message.assert_not_called()
        elif scenario == "whitespace_text":
            payload = {"thread_id": thread_id, "text": "   \n\t  "}
            with patch("app.api.routes_supervisor.supervisor_service", mock_supervisor_service):
                response = client.post("/supervisor/message", json=payload)
            assert response.status_code == expected_status
            assert response.json()["detail"] == expected_detail
            mock_supervisor_service.process_message.assert_not_called()
        elif scenario == "missing_thread_id":
            payload = {"text": "Hello"}
            response = client.post("/supervisor/message", json=payload)
            assert response.status_code == expected_status
            assert "detail" in response.json()
        elif scenario == "missing_text":
            payload = {"thread_id": thread_id}
            response = client.post("/supervisor/message", json=payload)
            assert response.status_code == expected_status
            assert "detail" in response.json()

    # TODO: SSE test hangs - needs proper async mocking strategy
    # def test_supervisor_sse_stream(self, client: TestClient):
    #     """Test supervisor SSE event stream endpoint existence."""
    #     # Arrange
    #     thread_id = "test-supervisor-thread-id"
    #
    #     # Mock both queue functions to avoid hanging
    #     mock_queue = AsyncMock()
    #     mock_queue.get = AsyncMock(side_effect=asyncio.TimeoutError())
    #
    #     # Act & Assert - just verify the endpoint responds
    #     with (
    #         patch("app.api.routes_supervisor.get_sse_queue", return_value=mock_queue),
    #         patch("app.core.app_state.drop_sse_queue"),
    #     ):
    #         response = client.get(f"/supervisor/sse/{thread_id}", timeout=1.0)
    #
    #         # Verify endpoint is accessible and returns correct content type
    #         assert response.status_code == 200
    #         assert "text/event-stream" in response.headers.get("content-type", "")

    @pytest.mark.parametrize(
        "has_error,expected_status",
        [
            (False, 200),
            (True, 500),
        ],
    )
    def test_debug_icebreaker(self, client: TestClient, has_error, expected_status):
        """Test debug icebreaker endpoint validates response contract."""
        user_id = str(uuid4())

        if has_error:
            error_message = "Database connection failed"
            with patch(
                "app.api.routes_supervisor.debug_icebreaker_flow",
                new_callable=AsyncMock,
                side_effect=Exception(error_message),
            ):
                response = client.get(f"/supervisor/debug/icebreaker/{user_id}")
                assert response.status_code == expected_status
                response_data = response.json()
                assert f"Debug failed: {error_message}" in response_data["detail"]
        else:
            expected_result = {
                "status": "success",
                "icebreakers_found": 3,
                "topics": ["budgeting", "retirement", "investing"],
            }
            with patch(
                "app.api.routes_supervisor.debug_icebreaker_flow",
                new_callable=AsyncMock,
                return_value=expected_result,
            ):
                response = client.get(f"/supervisor/debug/icebreaker/{user_id}")
                assert response.status_code == expected_status
                data = response.json()
                assert "status" in data and data["status"] == "success"
                assert "icebreakers_found" in data and isinstance(data["icebreakers_found"], int)
                assert "topics" in data and isinstance(data["topics"], list)
                assert all(isinstance(t, str) for t in data["topics"]) or len(data["topics"]) == 0

    @pytest.mark.parametrize(
        "skip_test,expected_status",
        [
            (True, None),  # Test will be skipped
            (False, 500),
        ],
    )
    def test_test_icebreaker_flow(
        self, client: TestClient, mock_supervisor_service, skip_test, expected_status
    ):
        """Test icebreaker flow test endpoint."""
        if skip_test:
            pytest.skip("Skipping due to external dependencies (DB, AWS, FOS API)")

        user_id = uuid4()
        error_message = "Initialization failed"
        mock_supervisor_service.initialize.side_effect = Exception(error_message)
        payload = {"user_id": str(user_id)}

        with patch("app.services.supervisor.supervisor_service", mock_supervisor_service):
            response = client.post("/supervisor/debug/test-icebreaker", json=payload)

        assert response.status_code == expected_status
        response_data = response.json()
        assert f"Test failed: {error_message}" in response_data["detail"]

    def test_initialize_supervisor_invalid_uuid(self, client: TestClient):
        """Test supervisor initialization with invalid UUID."""
        payload = {"user_id": "not-a-valid-uuid"}
        response = client.post("/supervisor/initialize", json=payload)
        assert response.status_code == 422
        response_data = response.json()
        assert "detail" in response_data

    # TODO: SSE test hangs - needs proper async mocking strategy
