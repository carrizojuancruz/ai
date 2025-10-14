"""
Tests for app/main.py FastAPI application configuration.

This test module covers:
- Application lifespan (startup/shutdown with error resilience)
- Health check endpoints (with error handling)

Following professional testing principles:
- Test behavior, not implementation
- Test business logic, not framework features
- Avoid brittle tests (no hardcoded config values)
- Avoid unreliable tests (no caplog assertions for INFO logs)
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


class TestLifespan:
    """Test application lifespan events (startup and shutdown)."""

    @pytest.mark.asyncio
    async def test_lifespan_startup_success(self):
        """Test successful application startup initializes all services."""
        with patch("app.db.session._get_engine") as mock_get_engine, \
             patch("app.core.app_state.warmup_aws_clients", new_callable=AsyncMock) as mock_warmup, \
             patch("app.core.app_state.start_finance_agent_cleanup_task", new_callable=AsyncMock) as mock_cleanup_start:

            from app.main import app as fastapi_app
            from app.main import lifespan

            async with lifespan(fastapi_app):
                pass

            mock_get_engine.assert_called_once()
            mock_warmup.assert_called_once()
            mock_cleanup_start.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("failing_service,exception_msg", [
        ("db", "DB connection failed"),
        ("aws", "AWS warmup failed"),
        ("cleanup", "Cleanup task failed"),
    ])
    async def test_lifespan_startup_continues_on_failure(self, failing_service, exception_msg):
        """Test application startup continues even when a service fails to initialize.

        This is critical behavior - the app should be resilient to individual service failures.
        """
        with patch("app.db.session._get_engine") as mock_db, \
             patch("app.core.app_state.warmup_aws_clients", new_callable=AsyncMock) as mock_aws, \
             patch("app.core.app_state.start_finance_agent_cleanup_task", new_callable=AsyncMock) as mock_cleanup:

            if failing_service == "db":
                mock_db.side_effect = Exception(exception_msg)
            elif failing_service == "aws":
                mock_aws.side_effect = Exception(exception_msg)
            elif failing_service == "cleanup":
                mock_cleanup.side_effect = Exception(exception_msg)

            from app.main import app as fastapi_app
            from app.main import lifespan

            async with lifespan(fastapi_app):
                pass

            if failing_service != "db":
                mock_db.assert_called_once()
            if failing_service != "aws":
                mock_aws.assert_called_once()
            if failing_service != "cleanup":
                mock_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_shutdown_success(self):
        """Test successful application shutdown disposes all resources."""
        with patch("app.db.session._get_engine"), \
             patch("app.core.app_state.warmup_aws_clients", new_callable=AsyncMock), \
             patch("app.core.app_state.start_finance_agent_cleanup_task", new_callable=AsyncMock), \
             patch("app.db.session.dispose_engine", new_callable=AsyncMock) as mock_dispose_db, \
             patch("app.core.app_state.dispose_aws_clients") as mock_dispose_aws, \
             patch("app.core.app_state.dispose_finance_agent_cleanup_task") as mock_dispose_cleanup:

            from app.main import app as fastapi_app
            from app.main import lifespan

            async with lifespan(fastapi_app):
                pass

            mock_dispose_db.assert_called_once()
            mock_dispose_aws.assert_called_once()
            mock_dispose_cleanup.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("failing_service", ["db", "aws", "cleanup"])
    async def test_lifespan_shutdown_continues_on_failure(self, failing_service):
        """Test application shutdown continues even when disposal fails.

        This ensures graceful shutdown - one failure shouldn't prevent cleanup of other resources.
        """
        with patch("app.db.session._get_engine"), \
             patch("app.core.app_state.warmup_aws_clients", new_callable=AsyncMock), \
             patch("app.core.app_state.start_finance_agent_cleanup_task", new_callable=AsyncMock), \
             patch("app.db.session.dispose_engine", new_callable=AsyncMock) as mock_dispose_db, \
             patch("app.core.app_state.dispose_aws_clients") as mock_dispose_aws, \
             patch("app.core.app_state.dispose_finance_agent_cleanup_task") as mock_dispose_cleanup:

            if failing_service == "db":
                mock_dispose_db.side_effect = Exception("DB disposal failed")
            elif failing_service == "aws":
                mock_dispose_aws.side_effect = Exception("AWS disposal failed")
            elif failing_service == "cleanup":
                mock_dispose_cleanup.side_effect = Exception("Cleanup disposal failed")

            from app.main import app as fastapi_app
            from app.main import lifespan

            async with lifespan(fastapi_app):
                pass

            mock_dispose_db.assert_called_once()
            mock_dispose_aws.assert_called_once()
            mock_dispose_cleanup.assert_called_once()


class TestHealthEndpoints:
    """Test health check endpoints return correct status based on system state."""

    def test_health_check_returns_healthy_status(self):
        """Test /health endpoint returns healthy status with correct message."""
        from app.main import app

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert "Verde AI" in data["message"]

    @pytest.mark.asyncio
    async def test_database_health_check_healthy(self):
        """Test /health/database returns healthy status when DB connection is working."""
        with patch("app.db.session._get_engine"), \
             patch("app.db.session._health_check_connection", new_callable=AsyncMock) as mock_health_check, \
             patch("app.db.session.get_connection_stats") as mock_stats:

            mock_health_check.return_value = True
            mock_stats.return_value = {
                "pool_size": 5,
                "checked_out": 1,
                "overflow": 0,
            }

            from app.main import app

            client = TestClient(app)
            response = client.get("/health/database")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "healthy"
            assert data["database"]["connection_healthy"] is True
            assert "pool_stats" in data["database"]
            assert data["database"]["pool_stats"]["pool_size"] == 5

    @pytest.mark.asyncio
    async def test_database_health_check_unhealthy(self):
        """Test /health/database returns unhealthy status when DB check fails."""
        with patch("app.db.session._get_engine"), \
             patch("app.db.session._health_check_connection", new_callable=AsyncMock) as mock_health_check, \
             patch("app.db.session.get_connection_stats") as mock_stats:

            mock_health_check.return_value = False
            mock_stats.return_value = {}

            from app.main import app

            client = TestClient(app)
            response = client.get("/health/database")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "unhealthy"
            assert data["database"]["connection_healthy"] is False

    @pytest.mark.asyncio
    async def test_database_health_check_handles_exceptions(self):
        """Test /health/database handles database errors gracefully without crashing."""
        with patch("app.db.session._get_engine") as mock_engine:

            mock_engine.side_effect = Exception("Database connection error")

            from app.main import app

            client = TestClient(app)
            response = client.get("/health/database")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "error"
            assert data["database"]["connection_healthy"] is False
            assert "error" in data["database"]
            assert "Database connection error" in data["database"]["error"]
