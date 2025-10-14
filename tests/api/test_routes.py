"""Tests for app/api/routes.py."""

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest


class TestGetOnboardingStatus:
    """Tests for get_onboarding_status endpoint."""

    def test_valid_user_id_success(self, client, mocker):
        """Test successful status retrieval validates contract and UUID parsing."""
        user_id = str(uuid4())
        mock_status = {"active": True, "onboarding_done": False, "thread_id": "123"}

        mock_fn = mocker.patch("app.api.routes.get_onboarding_status_for_user", return_value=mock_status)

        response = client.get(f"/onboarding/status/{user_id}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data.get("active"), bool)
        assert isinstance(data.get("onboarding_done"), bool)
        # thread_id may be present depending on status
        if "thread_id" in data:
            assert isinstance(data["thread_id"], (str, type(None)))

        # Ensure the route parsed UUID and passed it to the function
        called_arg = mock_fn.call_args[0][0]
        assert isinstance(called_arg, UUID)
        assert called_arg == UUID(user_id)

    def test_invalid_user_id_raises_400(self, client):
        """Test that invalid user_id raises HTTPException 400."""
        invalid_user_id = "not-a-uuid"

        response = client.get(f"/onboarding/status/{invalid_user_id}")

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid user_id"}

    def test_inactive_and_not_done_triggers_external_lookup(self, client, mocker):
        """When inactive and not done, external lookup can mark onboarding as done."""
        user_id = str(uuid4())
        mock_status = {"active": False, "onboarding_done": False}
        updated_status = {
            "active": False,
            "onboarding_done": True,
            "thread_id": None,
            "current_flow_step": None,
        }

        mocker.patch("app.api.routes.get_onboarding_status_for_user", return_value=mock_status)
        mock_repo_class = mocker.patch("app.services.external_context.user.repository.ExternalUserRepository")
        mock_repo_instance = mock_repo_class.return_value
        mock_repo_instance.get_by_id = AsyncMock(return_value={"some": "data"})
        mock_ctx_class = mocker.patch("app.models.UserContext")
        mock_ctx_instance = mock_ctx_class.return_value
        mock_ctx_instance.ready_for_orchestrator = True
        mocker.patch("app.services.external_context.user.mapping.map_ai_context_to_user_context")

        response = client.get(f"/onboarding/status/{user_id}")

        assert response.status_code == 200
        assert response.json() == updated_status
        mock_repo_instance.get_by_id.assert_called_once()

    def test_external_lookup_fails_gracefully(self, client, mocker):
        """External lookup failures are swallowed; original status is returned."""
        user_id = str(uuid4())
        mock_status = {"active": False, "onboarding_done": False}

        mocker.patch("app.api.routes.get_onboarding_status_for_user", return_value=mock_status)
        mocker.patch("app.services.external_context.user.repository.ExternalUserRepository", side_effect=Exception("DB error"))

        response = client.get(f"/onboarding/status/{user_id}")

        assert response.status_code == 200
        assert response.json() == mock_status


class TestInitializeOnboarding:
    """Tests for initialize_onboarding endpoint."""

    @pytest.mark.parametrize("payload,expected_user_id,description", [
        ({"user_id": "test-user"}, "test-user", "with user_id"),
        ({}, None, "without user_id"),
    ])
    def test_initialize_returns_contract_fields(self, client, mocker, payload, expected_user_id, description):
        """Initialization returns contract fields and forwards user_id correctly."""
        mock_result = {
            "thread_id": "123",
            "welcome": "Welcome!",
            "sse_url": "/onboarding/sse/123"
        }

        init_mock = mocker.patch("app.api.routes.onboarding_service.initialize", new=AsyncMock(return_value=mock_result))

        response = client.post("/onboarding/initialize", json=payload)

        assert response.status_code == 200, f"Failed for {description}"
        data = response.json()
        assert set(["thread_id", "welcome", "sse_url"]).issubset(data.keys())
        assert isinstance(data["thread_id"], str)
        assert isinstance(data["welcome"], str)
        assert isinstance(data["sse_url"], str)
        init_mock.assert_awaited_once_with(user_id=expected_user_id)


class TestOnboardingMessage:
    """Tests for onboarding_message endpoint."""

    @pytest.mark.parametrize("payload,expected_args,description", [
        (
            {"thread_id": "123", "type": "choice", "choice_ids": ["opt1"]},
            {"thread_id": "123", "type": "choice", "text": None, "choice_ids": ["opt1"], "action": None},
            "choice message"
        ),
        (
            {"thread_id": "123", "type": "text", "text": "Hello"},
            {"thread_id": "123", "type": "text", "text": "Hello", "choice_ids": None, "action": None},
            "text message"
        ),
    ])
    def test_message_validates_contract_and_forwards_args(self, client, mocker, payload, expected_args, description):
        """Test successful message processing validates contract and forwards correct args."""
        mock_result = {"status": "processed"}

        proc_mock = mocker.patch("app.api.routes.onboarding_service.process_message", new=AsyncMock(return_value=mock_result))

        response = client.post("/onboarding/message", json=payload)

        assert response.status_code == 200, f"Failed for {description}"
        data = response.json()
        assert data.get("status") == "processed"
        proc_mock.assert_awaited_once_with(**expected_args)

    @pytest.mark.parametrize("payload,expected_error,description", [
        (
            {"thread_id": "123", "type": "choice"},
            "choice_ids required for type 'choice'",
            "choice without choice_ids"
        ),
        (
            {"thread_id": "123", "type": "text"},
            "text required for type 'text'",
            "text without text field"
        ),
    ])
    def test_message_validation_errors(self, client, payload, expected_error, description):
        """Test that missing required fields return 400 with proper detail."""
        response = client.post("/onboarding/message", json=payload)

        assert response.status_code == 400, f"Failed for {description}"
        assert response.json() == {"detail": expected_error}


class TestOnboardingDone:
    """Tests for onboarding_done endpoint."""

    def test_done_success(self, client, mocker):
        """Onboarding done returns contract and emits status events."""
        thread_id = "123"
        mock_state = {"active": True}
        mock_queue = mocker.AsyncMock()

        mocker.patch("app.api.routes.get_thread_state", return_value=mock_state)
        mocker.patch("app.api.routes.get_sse_queue", return_value=mock_queue)
        fin_mock = mocker.patch("app.api.routes.onboarding_service.finalize", new=AsyncMock())

        response = client.post(f"/onboarding/done/{thread_id}")

        assert response.status_code == 200
        assert response.json() == {"status": "done"}
        fin_mock.assert_awaited_once_with(thread_id=thread_id)
        # Verify queue received processing and done events
        calls = [c.args[0] for c in mock_queue.put.await_args_list]
        assert any(isinstance(c, dict) and c.get("event") == "onboarding.status" and c.get("data", {}).get("status") == "processing" for c in calls)
        assert any(isinstance(c, dict) and c.get("event") == "onboarding.status" and c.get("data", {}).get("status") == "done" for c in calls)

    def test_done_thread_not_found_raises_404(self, client, mocker):
        """Test done with invalid thread_id raises 404."""
        thread_id = "invalid"

        mocker.patch("app.api.routes.get_thread_state", return_value=None)

        response = client.post(f"/onboarding/done/{thread_id}")

        assert response.status_code == 404
        assert response.json() == {"detail": "Thread not found"}


