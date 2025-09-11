"""Cost aggregation utilities for processing and grouping cost data."""

from datetime import date
from typing import Dict, List

from .models import AdminCostSummary, DailyCostFields, UserCostSummary, UserDailyCost, UserDailyCosts


def aggregate_by_user(costs: List[UserCostSummary]) -> Dict[str, Dict[str, float]]:
    """Aggregate costs by user ID."""
    user_aggregates = {}

    for cost in costs:
        uid = cost.user_id
        if uid not in user_aggregates:
            user_aggregates[uid] = {'total_cost': 0.0, 'trace_count': 0}

        user_aggregates[uid]['total_cost'] += cost.total_cost
        user_aggregates[uid]['trace_count'] += cost.trace_count

    return user_aggregates


def create_admin_summaries(user_aggregates: Dict[str, Dict[str, float]]) -> List[AdminCostSummary]:
    """Create AdminCostSummary objects from aggregated data."""
    return [
        AdminCostSummary(
            user_id=uid,
            total_cost=data['total_cost'],
            trace_count=int(data['trace_count'])
        )
        for uid, data in user_aggregates.items()
    ]


def create_daily_cost_fields(costs: List[UserCostSummary], target_date: date) -> DailyCostFields:
    """Create DailyCostFields from costs for a specific date."""
    total_cost = sum(cost.total_cost for cost in costs)
    total_traces = sum(cost.trace_count for cost in costs)

    return DailyCostFields(
        date=target_date.isoformat(),
        total_cost=total_cost,
        trace_count=total_traces
    )


def group_daily_costs_by_user(daily_costs: List[UserDailyCost]) -> List[UserDailyCosts]:
    """Group daily costs by user ID."""
    user_costs_dict = {}

    for user_cost in daily_costs:
        if user_cost.user_id not in user_costs_dict:
            user_costs_dict[user_cost.user_id] = []

        daily_cost_field = DailyCostFields(
            total_cost=user_cost.total_cost,
            trace_count=user_cost.trace_count,
            date=user_cost.date
        )
        user_costs_dict[user_cost.user_id].append(daily_cost_field)

    return [
        UserDailyCosts(user_id=user_id, daily_costs=daily_costs)
        for user_id, daily_costs in user_costs_dict.items()
    ]
