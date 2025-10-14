"""Tests for nudge evaluation routes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


class TestNudgeEvalRoutes:
    """Test suite for nudge evaluation API routes."""

    @pytest.fixture
    def client(self):
        """Test client for FastAPI app."""
        return TestClient(app)

    @pytest.mark.parametrize(
        "nudge_type,extra_fields,uses_add_task",
        [
            ("static_bill", {}, False),
            (
                "info_based",
                {"nudge_id": "test_nudge_123", "notification_text": "Test notification", "preview_text": "Test preview"},
                True,
            ),
        ],
    )
    @patch("app.api.routes_nudge_eval.get_nudge_evaluator")
    @patch("app.api.routes_nudge_eval.get_sqs_manager")
    @patch("app.api.routes_nudge_eval.iter_active_users")
    @patch("app.api.routes_nudge_eval.BackgroundTasks.add_task", new_callable=MagicMock)
    def test_evaluate_nudges_success(
        self,
        mock_add_task,
        mock_iter_active_users,
        mock_get_sqs_manager,
        mock_get_nudge_evaluator,
        client,
        nudge_type,
        extra_fields,
        uses_add_task,
    ):
        """Test successful nudge evaluation validates API contract."""
        mock_evaluator = MagicMock()
        mock_evaluator.evaluate_nudges_batch = AsyncMock(
            return_value={"evaluated": 3, "queued": 2, "skipped": 1}
        )
        mock_get_nudge_evaluator.return_value = mock_evaluator

        mock_sqs_manager = MagicMock()
        mock_get_sqs_manager.return_value = mock_sqs_manager

        async def mock_users_generator():
            yield ["user1", "user2", "user3"]

        mock_iter_active_users.return_value = mock_users_generator()

        request_data = {"nudge_type": nudge_type, **extra_fields}

        response = client.post("/nudges/evaluate", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert "status" in data and data["status"] == "started"
        assert "message" in data and isinstance(data["message"], str)
        assert "task_id" in data and isinstance(data["task_id"], str)
        if uses_add_task:
            mock_add_task.assert_called_once()

    @pytest.mark.parametrize(
        "config_disabled,missing_fields,background_error,expected_status,expected_message",
        [
            (True, False, False, 200, "Nudges are currently disabled"),
            (False, True, False, 400, "info_based nudges require nudge_id, notification_text, and preview_text"),
            (False, False, True, 500, "Failed to start evaluation"),
        ],
    )
    @patch("app.api.routes_nudge_eval.BackgroundTasks.add_task", new_callable=MagicMock)
    @patch("app.api.routes_nudge_eval.config")
    def test_evaluate_nudges_error_cases(
        self, mock_config, mock_add_task, client, config_disabled, missing_fields, background_error, expected_status, expected_message
    ):
        """Test nudge evaluation error scenarios."""
        if config_disabled:
            mock_config.NUDGES_ENABLED = False
            request_data = {"nudge_type": "static_bill"}
        elif missing_fields:
            mock_config.NUDGES_ENABLED = True
            request_data = {"nudge_type": "info_based"}
        else:  # background_error
            mock_config.NUDGES_ENABLED = True
            mock_add_task.side_effect = Exception("Test error")
            request_data = {"nudge_type": "static_bill"}

        response = client.post("/nudges/evaluate", json=request_data)

        assert response.status_code == expected_status
        data = response.json()
        if expected_status == 200:
            assert data["status"] == "skipped"
            assert data["message"] == expected_message
        else:
            assert expected_message in data["detail"]

    @pytest.mark.parametrize(
        "use_priority_override,expected_status,expected_msg_id,has_error",
        [
            (False, "queued", "test_msg_123", False),
            (True, "queued", "test_msg_456", False),
            (False, None, None, True),
        ],
    )
    @patch("app.api.routes_nudge_eval.get_nudge_evaluator")
    def test_trigger_nudge_manual(
        self, mock_get_nudge_evaluator, client, use_priority_override, expected_status, expected_msg_id, has_error
    ):
        """Test manual nudge trigger with various options and error handling."""
        if has_error:
            mock_get_nudge_evaluator.side_effect = Exception("Test trigger error")
            request_data = {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "nudge_type": "static_bill",
            }
            response = client.post("/nudges/trigger", json=request_data)
            assert response.status_code == 500
            data = response.json()
            assert "Failed to trigger nudge" in data["detail"]
        else:
            mock_evaluator = MagicMock()
            mock_evaluator.evaluate_nudges_batch = AsyncMock(
                return_value={"results": [{"status": expected_status, "message_id": expected_msg_id}]}
            )
            mock_get_nudge_evaluator.return_value = mock_evaluator

            request_data = {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "nudge_type": "memory_icebreaker" if not use_priority_override else "static_bill",
            }
            if use_priority_override:
                request_data.update({"force": True, "priority_override": 10})

            response = client.post("/nudges/trigger", json=request_data)
            assert response.status_code == 200
            data = response.json()
            assert "status" in data and data["status"] == expected_status
            assert "message_id" in data and data["message_id"] == expected_msg_id
            if use_priority_override:
                assert "priority_override" in data and data["priority_override"] == 10

    @pytest.mark.parametrize(
        "has_error,expected_status,expected_depth",
        [
            (False, "healthy", 5),
            (True, "unhealthy", None),
        ],
    )
    @patch("app.api.routes_nudge_eval.get_sqs_manager")
    @patch("app.api.routes_nudge_eval.config")
    def test_get_nudge_health(
        self, mock_config, mock_get_sqs_manager, client, has_error, expected_status, expected_depth
    ):
        """Test health check in success and error scenarios."""
        mock_config.NUDGES_ENABLED = True
        mock_config.SQS_NUDGES_AI_ICEBREAKER = ["https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"]

        if has_error:
            mock_get_sqs_manager.side_effect = Exception("SQS connection failed")
        else:
            mock_sqs_manager = MagicMock()
            mock_sqs_manager.get_queue_depth = AsyncMock(return_value=expected_depth)
            mock_get_sqs_manager.return_value = mock_sqs_manager

        response = client.get("/nudges/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == expected_status
        if has_error:
            assert "error" in data and "SQS connection failed" in data["error"]
        else:
            assert data["nudges_enabled"] is True
            assert data["queue_depth"] == expected_depth
            assert data["queue_url"] == ["https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"]
