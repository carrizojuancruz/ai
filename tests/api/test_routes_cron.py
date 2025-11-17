"""Tests for routes_cron.py."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.schemas.cron import BackgroundSyncStartedResponse


class TestCronRoutes:
    """Test cases for cron routes."""

    def test_sync_all_sources_success(self, client: TestClient):
        """Test successful sync_all_sources endpoint: contract and types."""
        expected_job_id = "test-job-id"

        with patch("app.api.routes_cron.uuid4") as mock_uuid, \
             patch("app.api.routes_cron.BackgroundTasks.add_task", new_callable=MagicMock):

            mock_uuid.return_value = expected_job_id

            response = client.post("/cron/knowledge-base")

            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == expected_job_id
            assert "sync" in data["message"].lower() and "background" in data["message"].lower()
            assert isinstance(data.get("started_at"), str)
            # started_at should be ISO8601 parseable
            from datetime import datetime as dt
            dt.fromisoformat(data["started_at"])  # will raise if invalid

            # Schema validation
            BackgroundSyncStartedResponse(**data)

    def test_sync_all_sources_with_limit_success(self, client: TestClient):
        """Test sync_all_sources with limit: contract and param passthrough."""
        expected_job_id = "test-job-id-limited"
        limit = 5

        with patch("app.api.routes_cron.uuid4") as mock_uuid, \
             patch("app.api.routes_cron.BackgroundTasks.add_task") as mock_add_task:

            mock_uuid.return_value = expected_job_id

            response = client.post("/cron/knowledge-base", params={"limit": limit})

            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == expected_job_id
            assert "sync" in data["message"].lower() and "background" in data["message"].lower()
            assert isinstance(data.get("started_at"), str)

            # Ensure background task scheduled with correct args
            # First arg is the function, following args include job_id
            assert mock_add_task.call_count == 1
            _, call_args, call_kwargs = mock_add_task.mock_calls[0]
            assert expected_job_id in call_args or expected_job_id in call_kwargs.values()

    @pytest.mark.parametrize("mock_target,side_effect,description", [
        ("app.api.routes_cron.BackgroundTasks.add_task", Exception("Background task failed"), "background task setup"),
        ("app.api.routes_cron.uuid4", Exception("UUID generation failed"), "UUID generation"),
    ])
    def test_sync_all_sources_handles_exceptions(self, client: TestClient, mock_target, side_effect, description):
        """Test sync_all_sources endpoint handles exceptions during operation."""
        with patch(mock_target, side_effect=side_effect):
            response = client.post("/cron/knowledge-base")

            assert response.status_code == 500, f"Failed for {description}"
            response_data = response.json()
            assert "Failed to start sync operation" in response_data["detail"]
            assert str(side_effect.args[0]) in response_data["detail"]


