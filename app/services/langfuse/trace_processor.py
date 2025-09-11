"""Trace processing utilities for extracting and filtering cost data."""

import json
import logging
from datetime import date
from typing import List, Optional

from .models import UserCostSummary

logger = logging.getLogger(__name__)


def extract_user_id(trace) -> Optional[str]:
    """Extract user ID from trace metadata."""
    try:
        metadata = _get_metadata(trace)
        if not metadata:
            return None

        if isinstance(metadata, dict):
            return metadata.get('user_id')
        elif isinstance(metadata, str):
            parsed = json.loads(metadata)
            return parsed.get('user_id')
    except (json.JSONDecodeError, AttributeError, KeyError) as e:
        logger.debug(f"Failed to extract user_id from trace: {e}")

    return None


def extract_cost(trace) -> float:
    """Extract cost from trace with fallback options."""
    cost_fields = ['totalCost', 'cost', 'total_cost']

    try:
        for field in cost_fields:
            if hasattr(trace, field):
                value = getattr(trace, field)
                if value is not None:
                    return float(value)

            if isinstance(trace, dict) and field in trace:
                value = trace[field]
                if value is not None:
                    return float(value)
    except (ValueError, TypeError) as e:
        logger.debug(f"Failed to extract cost from trace: {e}")

    return 0.0


def process_traces(
    traces_data: List[dict],
    target_date: date,
    user_id: Optional[str] = None,
    exclude_user_metadata: bool = False
) -> List[UserCostSummary]:
    """Process traces into cost summaries with optional filtering."""
    user_costs = {}

    for trace in traces_data:
        trace_user_id = extract_user_id(trace)

        if not _should_include_trace(trace_user_id, user_id, exclude_user_metadata):
            continue

        cost = extract_cost(trace)
        _accumulate_cost(user_costs, trace_user_id, cost)

    return _create_cost_summaries(user_costs, target_date)


def _get_metadata(trace):
    """Get metadata from trace object or dict."""
    if isinstance(trace, dict) and 'metadata' in trace:
        return trace['metadata']
    elif hasattr(trace, 'metadata'):
        return trace.metadata
    return None


def _should_include_trace(
    trace_user_id: Optional[str],
    filter_user_id: Optional[str],
    exclude_user_metadata: bool
) -> bool:
    """Determine if trace should be included based on filters."""
    if filter_user_id and trace_user_id != filter_user_id:
        return False
    return not (exclude_user_metadata and trace_user_id is not None)


def _accumulate_cost(user_costs: dict, user_id: Optional[str], cost: float):
    """Accumulate cost for a user."""
    if user_id not in user_costs:
        user_costs[user_id] = {'cost': 0.0, 'tokens': 0, 'traces': 0}

    user_costs[user_id]['cost'] += cost
    user_costs[user_id]['traces'] += 1


def _create_cost_summaries(user_costs: dict, target_date: date) -> List[UserCostSummary]:
    """Create UserCostSummary objects from accumulated costs."""
    return [
        UserCostSummary(
            user_id=uid,
            date=target_date,
            total_cost=data['cost'],
            total_tokens=data['tokens'],
            trace_count=data['traces']
        )
        for uid, data in user_costs.items()
    ]
