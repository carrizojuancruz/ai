"""Tests for langfuse/aggregators.py - cost aggregation business logic."""

from datetime import date

import pytest

from app.services.langfuse.aggregators import (
    aggregate_by_user,
    create_admin_summaries,
    create_daily_cost_fields,
    group_daily_costs_by_user,
)
from app.services.langfuse.models import (
    DailyCostFields,
    UserCostSummary,
    UserDailyCost,
)


@pytest.fixture
def test_date():
    """Fixture providing a test date for UserCostSummary objects."""
    return date(2024, 1, 15)


class TestAggregateByUser:
    """Test aggregate_by_user cost aggregation logic."""

    def test_single_user_single_cost(self, test_date):
        """Should aggregate single cost for single user."""
        costs = [UserCostSummary(user_id="user1", date=test_date, total_cost=10.50, trace_count=5)]

        result = aggregate_by_user(costs)

        assert result == {"user1": {"total_cost": 10.50, "trace_count": 5}}

    def test_single_user_multiple_costs(self, test_date):
        """Should sum costs for same user."""
        costs = [
            UserCostSummary(user_id="user1", date=test_date, total_cost=10.50, trace_count=5),
            UserCostSummary(user_id="user1", date=test_date, total_cost=5.25, trace_count=3),
            UserCostSummary(user_id="user1", date=test_date, total_cost=2.00, trace_count=1),
        ]

        result = aggregate_by_user(costs)

        assert result == {"user1": {"total_cost": 17.75, "trace_count": 9}}

    def test_multiple_users(self, test_date):
        """Should aggregate costs by user ID."""
        costs = [
            UserCostSummary(user_id="user1", date=test_date, total_cost=10.0, trace_count=5),
            UserCostSummary(user_id="user2", date=test_date, total_cost=20.0, trace_count=10),
            UserCostSummary(user_id="user3", date=test_date, total_cost=5.0, trace_count=2),
        ]

        result = aggregate_by_user(costs)

        assert result == {
            "user1": {"total_cost": 10.0, "trace_count": 5},
            "user2": {"total_cost": 20.0, "trace_count": 10},
            "user3": {"total_cost": 5.0, "trace_count": 2},
        }

    def test_multiple_users_with_repeated_entries(self, test_date):
        """Should sum costs for same users across multiple entries."""
        costs = [
            UserCostSummary(user_id="user1", date=test_date, total_cost=10.0, trace_count=5),
            UserCostSummary(user_id="user2", date=test_date, total_cost=20.0, trace_count=10),
            UserCostSummary(user_id="user1", date=test_date, total_cost=5.0, trace_count=3),
            UserCostSummary(user_id="user2", date=test_date, total_cost=15.0, trace_count=7),
        ]

        result = aggregate_by_user(costs)

        assert result == {
            "user1": {"total_cost": 15.0, "trace_count": 8},
            "user2": {"total_cost": 35.0, "trace_count": 17},
        }

    def test_empty_list(self):
        """Should return empty dict for empty input."""
        result = aggregate_by_user([])

        assert result == {}

    def test_zero_costs(self, test_date):
        """Should handle zero costs."""
        costs = [
            UserCostSummary(user_id="user1", date=test_date, total_cost=0.0, trace_count=0),
            UserCostSummary(user_id="user1", date=test_date, total_cost=0.0, trace_count=0),
        ]

        result = aggregate_by_user(costs)

        assert result == {"user1": {"total_cost": 0.0, "trace_count": 0}}

    def test_floating_point_precision(self, test_date):
        """Should handle floating point addition correctly."""
        costs = [
            UserCostSummary(user_id="user1", date=test_date, total_cost=0.1, trace_count=1),
            UserCostSummary(user_id="user1", date=test_date, total_cost=0.2, trace_count=1),
            UserCostSummary(user_id="user1", date=test_date, total_cost=0.3, trace_count=1),
        ]

        result = aggregate_by_user(costs)

        # Floating point should be close to 0.6
        assert abs(result["user1"]["total_cost"] - 0.6) < 0.0001
        assert result["user1"]["trace_count"] == 3


class TestCreateAdminSummaries:
    """Test create_admin_summaries conversion logic."""

    def test_single_user(self):
        """Should create AdminCostSummary for single user."""
        user_aggregates = {"user1": {"total_cost": 10.50, "trace_count": 5}}

        result = create_admin_summaries(user_aggregates)

        assert len(result) == 1
        assert result[0].user_id == "user1"
        assert result[0].total_cost == 10.50
        assert result[0].trace_count == 5

    def test_multiple_users(self):
        """Should create AdminCostSummary list for multiple users."""
        user_aggregates = {
            "user1": {"total_cost": 10.0, "trace_count": 5},
            "user2": {"total_cost": 20.0, "trace_count": 10},
            "user3": {"total_cost": 5.0, "trace_count": 2},
        }

        result = create_admin_summaries(user_aggregates)

        assert len(result) == 3
        user_ids = {summary.user_id for summary in result}
        assert user_ids == {"user1", "user2", "user3"}

    def test_empty_aggregates(self):
        """Should return empty list for empty input."""
        result = create_admin_summaries({})

        assert result == []

    def test_trace_count_conversion_to_int(self):
        """Should convert trace_count to int."""
        user_aggregates = {"user1": {"total_cost": 10.0, "trace_count": 5.0}}

        result = create_admin_summaries(user_aggregates)

        assert isinstance(result[0].trace_count, int)
        assert result[0].trace_count == 5

    def test_preserves_all_fields(self):
        """Should preserve all fields correctly."""
        user_aggregates = {
            "user1": {"total_cost": 123.456, "trace_count": 789},
        }

        result = create_admin_summaries(user_aggregates)

        assert result[0].user_id == "user1"
        assert result[0].total_cost == 123.456
        assert result[0].trace_count == 789


class TestCreateDailyCostFields:
    """Test create_daily_cost_fields aggregation logic."""

    def test_single_cost(self, test_date):
        """Should create DailyCostFields from single cost."""
        costs = [UserCostSummary(user_id="user1", date=test_date, total_cost=10.50, trace_count=5)]
        target_date = date(2024, 1, 15)

        result = create_daily_cost_fields(costs, target_date)

        assert result.date == "2024-01-15"
        assert result.total_cost == 10.50
        assert result.trace_count == 5

    def test_multiple_costs_summed(self, test_date):
        """Should sum costs from multiple users."""
        costs = [
            UserCostSummary(user_id="user1", date=test_date, total_cost=10.0, trace_count=5),
            UserCostSummary(user_id="user2", date=test_date, total_cost=20.0, trace_count=10),
            UserCostSummary(user_id="user3", date=test_date, total_cost=5.0, trace_count=2),
        ]
        target_date = date(2024, 1, 15)

        result = create_daily_cost_fields(costs, target_date)

        assert result.date == "2024-01-15"
        assert result.total_cost == 35.0
        assert result.trace_count == 17

    def test_empty_costs(self):
        """Should return zero totals for empty costs."""
        target_date = date(2024, 1, 15)

        result = create_daily_cost_fields([], target_date)

        assert result.date == "2024-01-15"
        assert result.total_cost == 0.0
        assert result.trace_count == 0

    def test_date_formatting(self, test_date):
        """Should format date as ISO string."""
        costs = [UserCostSummary(user_id="user1", date=test_date, total_cost=1.0, trace_count=1)]
        target_date = date(2024, 12, 31)

        result = create_daily_cost_fields(costs, target_date)

        assert result.date == "2024-12-31"

    def test_zero_costs(self, test_date):
        """Should handle zero costs."""
        costs = [
            UserCostSummary(user_id="user1", date=test_date, total_cost=0.0, trace_count=0),
            UserCostSummary(user_id="user2", date=test_date, total_cost=0.0, trace_count=0),
        ]
        target_date = date(2024, 1, 1)

        result = create_daily_cost_fields(costs, target_date)

        assert result.total_cost == 0.0
        assert result.trace_count == 0


class TestGroupDailyCostsByUser:
    """Test group_daily_costs_by_user grouping logic."""

    def test_single_user_single_day(self):
        """Should group single day cost for single user."""
        daily_costs = [
            UserDailyCost(user_id="user1", total_cost=10.0, trace_count=5, date="2024-01-15")
        ]

        result = group_daily_costs_by_user(daily_costs)

        assert len(result) == 1
        assert result[0].user_id == "user1"
        assert len(result[0].daily_costs) == 1
        assert result[0].daily_costs[0].total_cost == 10.0
        assert result[0].daily_costs[0].trace_count == 5
        assert result[0].daily_costs[0].date == "2024-01-15"

    def test_single_user_multiple_days(self):
        """Should group multiple days for single user."""
        daily_costs = [
            UserDailyCost(user_id="user1", total_cost=10.0, trace_count=5, date="2024-01-15"),
            UserDailyCost(user_id="user1", total_cost=20.0, trace_count=10, date="2024-01-16"),
            UserDailyCost(user_id="user1", total_cost=5.0, trace_count=2, date="2024-01-17"),
        ]

        result = group_daily_costs_by_user(daily_costs)

        assert len(result) == 1
        assert result[0].user_id == "user1"
        assert len(result[0].daily_costs) == 3
        dates = {cost.date for cost in result[0].daily_costs}
        assert dates == {"2024-01-15", "2024-01-16", "2024-01-17"}

    def test_multiple_users_single_day_each(self):
        """Should separate costs by user."""
        daily_costs = [
            UserDailyCost(user_id="user1", total_cost=10.0, trace_count=5, date="2024-01-15"),
            UserDailyCost(user_id="user2", total_cost=20.0, trace_count=10, date="2024-01-15"),
            UserDailyCost(user_id="user3", total_cost=5.0, trace_count=2, date="2024-01-15"),
        ]

        result = group_daily_costs_by_user(daily_costs)

        assert len(result) == 3
        user_ids = {uc.user_id for uc in result}
        assert user_ids == {"user1", "user2", "user3"}

    def test_multiple_users_multiple_days(self):
        """Should group by user with multiple days per user."""
        daily_costs = [
            UserDailyCost(user_id="user1", total_cost=10.0, trace_count=5, date="2024-01-15"),
            UserDailyCost(user_id="user2", total_cost=20.0, trace_count=10, date="2024-01-15"),
            UserDailyCost(user_id="user1", total_cost=15.0, trace_count=7, date="2024-01-16"),
            UserDailyCost(user_id="user2", total_cost=25.0, trace_count=12, date="2024-01-16"),
        ]

        result = group_daily_costs_by_user(daily_costs)

        assert len(result) == 2

        user1_data = next(uc for uc in result if uc.user_id == "user1")
        user2_data = next(uc for uc in result if uc.user_id == "user2")

        assert len(user1_data.daily_costs) == 2
        assert len(user2_data.daily_costs) == 2

    def test_empty_list(self):
        """Should return empty list for empty input."""
        result = group_daily_costs_by_user([])

        assert result == []

    def test_preserves_cost_fields(self):
        """Should preserve all DailyCostFields attributes."""
        daily_costs = [
            UserDailyCost(user_id="user1", total_cost=123.456, trace_count=789, date="2024-06-15")
        ]

        result = group_daily_costs_by_user(daily_costs)

        assert result[0].daily_costs[0].total_cost == 123.456
        assert result[0].daily_costs[0].trace_count == 789
        assert result[0].daily_costs[0].date == "2024-06-15"

    def test_order_preservation(self):
        """Should maintain order of daily costs as encountered."""
        daily_costs = [
            UserDailyCost(user_id="user1", total_cost=10.0, trace_count=5, date="2024-01-15"),
            UserDailyCost(user_id="user1", total_cost=20.0, trace_count=10, date="2024-01-16"),
            UserDailyCost(user_id="user1", total_cost=5.0, trace_count=2, date="2024-01-17"),
        ]

        result = group_daily_costs_by_user(daily_costs)

        # Should preserve insertion order
        assert result[0].daily_costs[0].date == "2024-01-15"
        assert result[0].daily_costs[1].date == "2024-01-16"
        assert result[0].daily_costs[2].date == "2024-01-17"

    def test_creates_dailycostfields_from_userdailycost(self):
        """Should convert UserDailyCost to DailyCostFields correctly."""
        daily_costs = [
            UserDailyCost(user_id="user1", total_cost=10.0, trace_count=5, date="2024-01-15")
        ]

        result = group_daily_costs_by_user(daily_costs)

        # Verify it's a DailyCostFields instance
        daily_cost_field = result[0].daily_costs[0]
        assert isinstance(daily_cost_field, DailyCostFields)
        assert hasattr(daily_cost_field, "total_cost")
        assert hasattr(daily_cost_field, "trace_count")
        assert hasattr(daily_cost_field, "date")
