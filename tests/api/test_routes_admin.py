"""Tests for app/api/routes_admin.py."""

from datetime import date

import pytest


class TestGetUserCosts:
    """Tests for get_user_costs endpoint."""

    @pytest.mark.parametrize("query_params,expected_service_args,description", [
        ("", (None, None, None), "no params (last 30 days)"),
        ("?user_id=test-user", (None, None, "test-user"), "user_id filter"),
        ("?from_date=2025-09-01&to_date=2025-09-30",
         (date(2025, 9, 1), date(2025, 9, 30), None), "date range"),
    ])
    def test_retrieves_user_costs_with_parameter_transformation(
        self, client, mocker, mock_langfuse_cost_service, query_params, expected_service_args, description
    ):
        """Test successful cost retrieval validates API contract and parameter transformation."""
        mock_result = [
            {"user_id": "user1", "total_cost": 10.5, "trace_count": 100},
            {"user_id": "user2", "total_cost": 5.0, "trace_count": 50}
        ]

        mock_langfuse_cost_service.get_users_costs.return_value = mock_result
        mocker.patch("app.api.routes_admin.LangfuseCostService.get_instance", return_value=mock_langfuse_cost_service)

        response = client.get(f"/admin/users/total-costs{query_params}")

        # API contract validation
        assert response.status_code == 200, f"Failed for {description}"
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        for item in data:
            assert "user_id" in item and isinstance(item["user_id"], str)
            assert "total_cost" in item and isinstance(item["total_cost"], (int, float))
            assert "trace_count" in item and isinstance(item["trace_count"], int)

        # Parameter transformation validation
        mock_langfuse_cost_service.get_users_costs.assert_called_once_with(*expected_service_args)

    def test_handles_service_error(self, client, mocker, mock_langfuse_cost_service):
        """Test that service errors raise HTTPException 500."""
        mock_langfuse_cost_service.get_users_costs.side_effect = Exception("Service error")
        mocker.patch("app.api.routes_admin.LangfuseCostService.get_instance", return_value=mock_langfuse_cost_service)

        response = client.get("/admin/users/total-costs")

        assert response.status_code == 500
        assert "Failed to fetch user costs" in response.json()["detail"]


class TestGetAllUsersDailyCostsGrouped:
    """Tests for get_all_users_daily_costs_grouped endpoint."""

    @pytest.mark.parametrize("query_params,expected_service_args,description", [
        ("", (None, None, None), "no params (last 30 days)"),
        ("?user_id=test-user&from_date=2025-09-01&to_date=2025-09-30",
         (date(2025, 9, 1), date(2025, 9, 30), "test-user"), "all parameters"),
    ])
    def test_retrieves_daily_costs_with_parameter_transformation(
        self, client, mocker, mock_langfuse_cost_service, query_params, expected_service_args, description
    ):
        """Test successful daily costs retrieval with parameter transformation."""
        mock_result = [
            {"user_id": "user1", "daily_costs": [{"date": "2025-09-01", "total_cost": 1.5, "trace_count": 10}]},
            {"user_id": "user2", "daily_costs": [{"date": "2025-09-01", "total_cost": 2.0, "trace_count": 15}]}
        ]

        mock_langfuse_cost_service.get_all_users_daily_costs_grouped.return_value = mock_result
        mocker.patch("app.api.routes_admin.LangfuseCostService.get_instance", return_value=mock_langfuse_cost_service)

        response = client.get(f"/admin/users/daily-costs{query_params}")

        assert response.status_code == 200, f"Failed for {description}"
        assert response.json() == mock_result
        mock_langfuse_cost_service.get_all_users_daily_costs_grouped.assert_called_once_with(*expected_service_args)

    def test_handles_service_error(self, client, mocker, mock_langfuse_cost_service):
        """Test that service errors raise HTTPException 500."""
        mock_langfuse_cost_service.get_all_users_daily_costs_grouped.side_effect = Exception("Service error")
        mocker.patch("app.api.routes_admin.LangfuseCostService.get_instance", return_value=mock_langfuse_cost_service)

        response = client.get("/admin/users/daily-costs")

        assert response.status_code == 500
        assert "Failed to fetch grouped daily costs" in response.json()["detail"]


class TestGetGuestCosts:
    """Tests for get_guest_costs endpoint."""

    @pytest.mark.parametrize("query_params,expected_service_args,description", [
        ("", (None, None), "no params (last 30 days)"),
        ("?from_date=2025-09-01&to_date=2025-09-30",
         (date(2025, 9, 1), date(2025, 9, 30)), "date parameters"),
    ])
    def test_retrieves_guest_costs_with_parameter_transformation(
        self, client, mocker, mock_langfuse_cost_service, query_params, expected_service_args, description
    ):
        """Test successful guest costs retrieval with parameter transformation."""
        mock_result = {"total_cost": 25.0, "trace_count": 500}

        mock_langfuse_cost_service.get_guest_costs.return_value = mock_result
        mocker.patch("app.api.routes_admin.LangfuseCostService.get_instance", return_value=mock_langfuse_cost_service)

        response = client.get(f"/admin/users/guest/costs{query_params}")

        assert response.status_code == 200, f"Failed for {description}"
        assert response.json() == mock_result
        mock_langfuse_cost_service.get_guest_costs.assert_called_once_with(*expected_service_args)

    def test_handles_service_error(self, client, mocker, mock_langfuse_cost_service):
        """Test that service errors raise HTTPException 500."""
        mock_langfuse_cost_service.get_guest_costs.side_effect = Exception("Service error")
        mocker.patch("app.api.routes_admin.LangfuseCostService.get_instance", return_value=mock_langfuse_cost_service)

        response = client.get("/admin/users/guest/costs")

        assert response.status_code == 500
        assert "Failed to fetch guest costs" in response.json()["detail"]

