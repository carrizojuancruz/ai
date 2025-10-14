"""Tests for langfuse/cost_service.py - focusing on business logic."""

import threading
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.langfuse.cost_service import LangfuseCostService
from app.services.langfuse.models import (
    GuestCostSummary,
    UserCostSummary,
)


class TestLangfuseCostServiceSingleton:
    """Test singleton pattern implementation."""

    def test_get_instance_returns_same_instance(self):
        """Test that get_instance returns the same instance every time."""
        with patch("app.services.langfuse.cost_service.LangfuseConfig.from_env_guest"), \
             patch("app.services.langfuse.cost_service.LangfuseConfig.from_env_supervisor"), \
             patch("app.services.langfuse.cost_service.Langfuse"), \
             patch("app.services.langfuse.cost_service.LangfuseHttpClient"):

            # Reset singleton for clean test
            import app.services.langfuse.cost_service as cost_service_module
            cost_service_module._instance = None

            # Get instances
            instance1 = LangfuseCostService.get_instance()
            instance2 = LangfuseCostService.get_instance()

            # Assert same instance
            assert instance1 is instance2

            # Cleanup
            cost_service_module._instance = None

    def test_singleton_thread_safety(self):
        """Test that singleton is thread-safe."""
        with patch("app.services.langfuse.cost_service.LangfuseConfig.from_env_guest"), \
             patch("app.services.langfuse.cost_service.LangfuseConfig.from_env_supervisor"), \
             patch("app.services.langfuse.cost_service.Langfuse"), \
             patch("app.services.langfuse.cost_service.LangfuseHttpClient"):

            # Reset singleton
            import app.services.langfuse.cost_service as cost_service_module
            cost_service_module._instance = None

            instances = []

            def get_instance():
                instances.append(LangfuseCostService.get_instance())

            # Create multiple threads
            threads = [threading.Thread(target=get_instance) for _ in range(10)]

            # Start all threads
            for thread in threads:
                thread.start()

            # Wait for completion
            for thread in threads:
                thread.join()

            # Assert all instances are the same
            assert len(set(id(inst) for inst in instances)) == 1

            # Cleanup
            cost_service_module._instance = None


class TestLangfuseCostServiceInitialization:
    """Test client initialization."""

    @patch("app.services.langfuse.cost_service.LangfuseHttpClient")
    @patch("app.services.langfuse.cost_service.Langfuse")
    @patch("app.services.langfuse.cost_service.LangfuseConfig")
    def test_initialize_clients_creates_guest_and_supervisor(self, mock_config_cls, mock_langfuse_cls, mock_http_client_cls):
        """Test that initialization creates both guest and supervisor clients."""
        # Setup mock configs
        mock_guest_config = MagicMock()
        mock_guest_config.public_key = "guest_public"
        mock_guest_config.secret_key = "guest_secret"
        mock_guest_config.host = "https://guest.langfuse.com"

        mock_supervisor_config = MagicMock()
        mock_supervisor_config.public_key = "supervisor_public"
        mock_supervisor_config.secret_key = "supervisor_secret"
        mock_supervisor_config.host = "https://supervisor.langfuse.com"

        mock_config_cls.from_env_guest.return_value = mock_guest_config
        mock_config_cls.from_env_supervisor.return_value = mock_supervisor_config

        # Execute
        service = LangfuseCostService()

        # Assert guest client created
        assert service.guest_config == mock_guest_config
        mock_langfuse_cls.assert_any_call(
            public_key="guest_public",
            secret_key="guest_secret",
            host="https://guest.langfuse.com"
        )

        # Assert supervisor client created
        assert service.supervisor_config == mock_supervisor_config
        mock_langfuse_cls.assert_any_call(
            public_key="supervisor_public",
            secret_key="supervisor_secret",
            host="https://supervisor.langfuse.com"
        )

        # Assert HTTP clients created
        assert mock_http_client_cls.call_count == 2


class TestGetCostsPerUserDate:
    """Test get_costs_per_user_date method."""

    @pytest.mark.asyncio
    @patch("app.services.langfuse.cost_service.LangfuseHttpClient")
    @patch("app.services.langfuse.cost_service.Langfuse")
    @patch("app.services.langfuse.cost_service.LangfuseConfig")
    async def test_delegates_to_get_costs_for_date(self, mock_config_cls, mock_langfuse_cls, mock_http_client_cls):
        """Test that method delegates to _get_costs_for_date with correct parameters."""
        # Setup
        mock_config_cls.from_env_guest.return_value = MagicMock()
        mock_config_cls.from_env_supervisor.return_value = MagicMock()

        target_date = date(2024, 1, 15)
        service = LangfuseCostService()
        service._get_costs_for_date = AsyncMock(return_value=[
            UserCostSummary(user_id="user1", date=target_date, total_cost=10.5, trace_count=5)
        ])

        # Execute - without user_id
        result = await service.get_costs_per_user_date(target_date)
        assert len(result) == 1
        service._get_costs_for_date.assert_called_with(target_date, None)

        # Execute - with user_id
        service._get_costs_for_date.reset_mock()
        await service.get_costs_per_user_date(target_date, user_id="user123")
        service._get_costs_for_date.assert_called_with(target_date, "user123")


class TestGetUsersCosts:
    """Test get_users_costs date range logic."""

    @pytest.mark.asyncio
    @patch("app.services.langfuse.cost_service.aggregators")
    @patch("app.services.langfuse.cost_service.date_utils")
    @patch("app.services.langfuse.cost_service.LangfuseHttpClient")
    @patch("app.services.langfuse.cost_service.Langfuse")
    @patch("app.services.langfuse.cost_service.LangfuseConfig")
    async def test_delegates_date_range_handling(self, mock_config_cls, mock_langfuse_cls,
                                                   mock_http_client_cls, mock_date_utils, mock_aggregators):
        """Test that method delegates date range logic to date_utils."""
        # Setup
        mock_config_cls.from_env_guest.return_value = MagicMock()
        mock_config_cls.from_env_supervisor.return_value = MagicMock()

        from_date = date(2024, 1, 1)
        to_date = date(2024, 1, 31)
        mock_date_utils.get_date_range.return_value = (from_date, to_date)

        service = LangfuseCostService()
        service._collect_costs_for_date_range = AsyncMock(return_value=[])
        mock_aggregators.aggregate_by_user.return_value = {}
        mock_aggregators.create_admin_summaries.return_value = []

        # Execute - no dates (should use defaults)
        await service.get_users_costs()
        mock_date_utils.get_date_range.assert_called_with(None, None)

        # Execute - from_date only
        mock_date_utils.get_date_range.reset_mock()
        await service.get_users_costs(from_date=from_date)
        mock_date_utils.get_date_range.assert_called_with(from_date, None)

        # Execute - both dates
        mock_date_utils.get_date_range.reset_mock()
        await service.get_users_costs(from_date=from_date, to_date=to_date)
        mock_date_utils.get_date_range.assert_called_with(from_date, to_date)

    @pytest.mark.asyncio
    @patch("app.services.langfuse.cost_service.aggregators")
    @patch("app.services.langfuse.cost_service.date_utils")
    @patch("app.services.langfuse.cost_service.LangfuseHttpClient")
    @patch("app.services.langfuse.cost_service.Langfuse")
    @patch("app.services.langfuse.cost_service.LangfuseConfig")
    async def test_error_handling_returns_empty_list(self, mock_config_cls, mock_langfuse_cls,
                                                      mock_http_client_cls, mock_date_utils, mock_aggregators):
        """Test that errors are caught and empty list returned."""
        # Setup
        mock_config_cls.from_env_guest.return_value = MagicMock()
        mock_config_cls.from_env_supervisor.return_value = MagicMock()

        mock_date_utils.get_date_range.side_effect = Exception("Date error")

        service = LangfuseCostService()

        # Execute
        result = await service.get_users_costs()

        # Assert
        assert result == []


class TestGetGuestCosts:
    """Test get_guest_costs aggregation logic."""

    @pytest.mark.asyncio
    @patch("app.services.langfuse.cost_service.date_utils")
    @patch("app.services.langfuse.cost_service.LangfuseHttpClient")
    @patch("app.services.langfuse.cost_service.Langfuse")
    @patch("app.services.langfuse.cost_service.LangfuseConfig")
    async def test_aggregates_total_cost_and_traces(self, mock_config_cls, mock_langfuse_cls,
                                                     mock_http_client_cls, mock_date_utils):
        """Test that guest costs are properly aggregated."""
        # Setup
        mock_config_cls.from_env_guest.return_value = MagicMock()
        mock_config_cls.from_env_supervisor.return_value = MagicMock()

        from_date = date(2024, 1, 1)
        to_date = date(2024, 1, 3)
        mock_date_utils.get_date_range.return_value = (from_date, to_date)

        service = LangfuseCostService()
        service._collect_guest_costs_for_date_range = AsyncMock(return_value=[
            UserCostSummary(user_id="guest1", date=date(2024, 1, 1), total_cost=5.0, trace_count=2),
            UserCostSummary(user_id="guest2", date=date(2024, 1, 2), total_cost=10.0, trace_count=3),
            UserCostSummary(user_id="guest3", date=date(2024, 1, 3), total_cost=15.0, trace_count=5),
        ])

        # Execute
        result = await service.get_guest_costs(from_date=from_date, to_date=to_date)

        # Assert
        assert isinstance(result, GuestCostSummary)
        assert result.total_cost == 30.0  # 5 + 10 + 15
        assert result.trace_count == 10  # 2 + 3 + 5

    @pytest.mark.asyncio
    @patch("app.services.langfuse.cost_service.date_utils")
    @patch("app.services.langfuse.cost_service.LangfuseHttpClient")
    @patch("app.services.langfuse.cost_service.Langfuse")
    @patch("app.services.langfuse.cost_service.LangfuseConfig")
    async def test_empty_costs_returns_zero_summary(self, mock_config_cls, mock_langfuse_cls,
                                                     mock_http_client_cls, mock_date_utils):
        """Test that empty costs return zero summary."""
        # Setup
        mock_config_cls.from_env_guest.return_value = MagicMock()
        mock_config_cls.from_env_supervisor.return_value = MagicMock()

        mock_date_utils.get_date_range.return_value = (date(2024, 1, 1), date(2024, 1, 1))

        service = LangfuseCostService()
        service._collect_guest_costs_for_date_range = AsyncMock(return_value=[])

        # Execute
        result = await service.get_guest_costs()

        # Assert
        assert result.total_cost == 0.0
        assert result.trace_count == 0

    @pytest.mark.asyncio
    @patch("app.services.langfuse.cost_service.date_utils")
    @patch("app.services.langfuse.cost_service.LangfuseHttpClient")
    @patch("app.services.langfuse.cost_service.Langfuse")
    @patch("app.services.langfuse.cost_service.LangfuseConfig")
    async def test_error_returns_zero_summary(self, mock_config_cls, mock_langfuse_cls,
                                               mock_http_client_cls, mock_date_utils):
        """Test that errors return zero summary."""
        # Setup
        mock_config_cls.from_env_guest.return_value = MagicMock()
        mock_config_cls.from_env_supervisor.return_value = MagicMock()

        mock_date_utils.get_date_range.side_effect = Exception("Date error")

        service = LangfuseCostService()

        # Execute
        result = await service.get_guest_costs()

        # Assert
        assert result.total_cost == 0.0
        assert result.trace_count == 0


class TestCreateUserDailyCostsForDate:
    """Test _create_user_daily_costs_for_date aggregation."""

    @pytest.mark.asyncio
    @patch("app.services.langfuse.cost_service.LangfuseHttpClient")
    @patch("app.services.langfuse.cost_service.Langfuse")
    @patch("app.services.langfuse.cost_service.LangfuseConfig")
    async def test_aggregates_costs_by_user(self, mock_config_cls, mock_langfuse_cls, mock_http_client_cls):
        """Test that costs are properly aggregated by user."""
        # Setup
        mock_config_cls.from_env_guest.return_value = MagicMock()
        mock_config_cls.from_env_supervisor.return_value = MagicMock()

        target_date = date(2024, 1, 15)
        service = LangfuseCostService()
        service._get_costs_for_date = AsyncMock(return_value=[
            UserCostSummary(user_id="user1", date=target_date, total_cost=5.0, trace_count=2),
            UserCostSummary(user_id="user1", date=target_date, total_cost=10.0, trace_count=3),
            UserCostSummary(user_id="user2", date=target_date, total_cost=7.5, trace_count=1),
        ])

        # Execute
        result = await service._create_user_daily_costs_for_date(target_date)

        # Assert
        assert len(result) == 2

        user1_cost = next((c for c in result if c.user_id == "user1"), None)
        assert user1_cost is not None
        assert user1_cost.total_cost == 15.0  # 5.0 + 10.0
        assert user1_cost.trace_count == 5  # 2 + 3
        assert user1_cost.date == "2024-01-15"

        user2_cost = next((c for c in result if c.user_id == "user2"), None)
        assert user2_cost is not None
        assert user2_cost.total_cost == 7.5
        assert user2_cost.trace_count == 1

    @pytest.mark.asyncio
    @patch("app.services.langfuse.cost_service.LangfuseHttpClient")
    @patch("app.services.langfuse.cost_service.Langfuse")
    @patch("app.services.langfuse.cost_service.LangfuseConfig")
    async def test_filters_out_null_user_ids(self, mock_config_cls, mock_langfuse_cls, mock_http_client_cls):
        """Test that entries with None user_id are filtered out."""
        # Setup
        mock_config_cls.from_env_guest.return_value = MagicMock()
        mock_config_cls.from_env_supervisor.return_value = MagicMock()

        target_date = date(2024, 1, 15)
        service = LangfuseCostService()
        service._get_costs_for_date = AsyncMock(return_value=[
            UserCostSummary(user_id="user1", date=target_date, total_cost=5.0, trace_count=2),
            UserCostSummary(user_id=None, date=target_date, total_cost=10.0, trace_count=3),
        ])

        # Execute
        result = await service._create_user_daily_costs_for_date(target_date)

        # Assert - only user1 should be included
        assert len(result) == 1
        assert result[0].user_id == "user1"

    @pytest.mark.asyncio
    @patch("app.services.langfuse.cost_service.LangfuseHttpClient")
    @patch("app.services.langfuse.cost_service.Langfuse")
    @patch("app.services.langfuse.cost_service.LangfuseConfig")
    async def test_empty_costs_returns_empty_list(self, mock_config_cls, mock_langfuse_cls, mock_http_client_cls):
        """Test that empty costs return empty list."""
        # Setup
        mock_config_cls.from_env_guest.return_value = MagicMock()
        mock_config_cls.from_env_supervisor.return_value = MagicMock()

        service = LangfuseCostService()
        service._get_costs_for_date = AsyncMock(return_value=[])

        target_date = date(2024, 1, 15)

        # Execute
        result = await service._create_user_daily_costs_for_date(target_date)

        # Assert
        assert result == []
