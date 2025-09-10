"""Admin routes for cost analytics - Essential endpoints only."""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.services.langfuse import LangfuseCostService
from app.services.langfuse.models import CostSummary, DailyCostResponse, AdminCostSummary

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


# Dependency
def get_cost_service() -> LangfuseCostService:
    """Dependency to get cost service instance."""
    return LangfuseCostService()


@router.get("/costs", response_model=List[AdminCostSummary])
async def get_user_costs(
    user_id: Optional[str] = Query(None, description="Filter by specific user ID (optional)"),  # noqa: B008
    from_date: Optional[date] = Query(None, description="Start date for range (YYYY-MM-DD)"),  # noqa: B008
    to_date: Optional[date] = Query(None, description="End date for range (YYYY-MM-DD)"),  # noqa: B008
    service: LangfuseCostService = Depends(get_cost_service)  # noqa: B008
) -> List[AdminCostSummary]:
    """Get costs for registered users with only essential fields: user_id, total_cost, trace_count.

    **Flexible Parameter Handling:**
    - No params: Historical costs for ALL users (all available data)
    - user_id only: Historical costs for specific user
    - from_date=to_date: All/specific users for single date
    - date range: All/specific users aggregated for date range

    **Always returns a list of AdminCostSummary objects with user_id, total_cost, and trace_count only.**

    **Examples:**
    - `/admin/users/costs` - All users historical costs
    - `/admin/users/costs?user_id=abc123` - Specific user historical costs
    - `/admin/users/costs?from_date=2025-09-10&to_date=2025-09-10` - All users for single date
    - `/admin/users/costs?user_id=abc123&from_date=2025-09-08&to_date=2025-09-10` - User costs for date range (simplified)

    **Note:** This endpoint only returns REGISTERED users (with user_id) and only essential cost fields.
    """
    try:
        return await service.get_users_costs(from_date, to_date, user_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch user costs: {str(e)}"
        ) from e


@router.get("/{user_id}/costs", response_model=List[DailyCostResponse])
async def get_user_daily_costs(
    user_id: str,
    from_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD). Default: 30 days ago"),  # noqa: B008
    to_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD). Default: today"),  # noqa: B008
    service: LangfuseCostService = Depends(get_cost_service)  # noqa: B008
) -> List[DailyCostResponse]:
    """Get daily cost breakdown for a specific user.

    Returns a list of daily costs where each object represents one day's activity.
    Default range is the last 30 days if no dates are provided.
    Results are sorted by date in descending order (most recent first).

    **Date Range Logic:**
    - **No params**: Last 30 days (from 30 days ago to today)
    - **from_date only**: From that date to today
    - **to_date only**: From that date to that date (single day)
    - **Both dates**: From from_date to to_date

    **Parameters:**
    - **user_id**: Required. The specific user ID to get costs for
    - **from_date**: Optional. Start date in YYYY-MM-DD format
    - **to_date**: Optional. End date in YYYY-MM-DD format

    **Example:**
    - `/admin/users/ba5c5db4-d3fb-4ca8-9445-1c221ea502a8/costs` - Last 30 days
    - `/admin/users/ba5c5db4-d3fb-4ca8-9445-1c221ea502a8/costs?from_date=2025-09-08` - From Sept 8 to today
    - `/admin/users/ba5c5db4-d3fb-4ca8-9445-1c221ea502a8/costs?from_date=2025-09-08&to_date=2025-09-10` - Specific range
    """
    try:
        return await service.get_user_daily_costs(user_id, from_date, to_date)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch daily costs for user {user_id}: {str(e)}"
        ) from e


@router.get("/guest/costs", response_model=CostSummary)
async def get_guest_costs(
    from_date: Optional[date] = Query(None, description="Start date for range (YYYY-MM-DD)"),  # noqa: B008
    to_date: Optional[date] = Query(None, description="End date for range (YYYY-MM-DD)"),  # noqa: B008
    service: LangfuseCostService = Depends(get_cost_service)  # noqa: B008
) -> CostSummary:
    """Get costs for guest users (users without user_id) with flexible date filtering.

    **Date Parameter Handling:**
    - No params: Last 7 days (default range for guest costs)
    - from_date=to_date: Guest costs for single date
    - date range: Guest costs aggregated for date range

    **Returns a single CostSummary object with user_id=null for all guest users.**

    **Examples:**
    - `/admin/users/guest/costs` - Guest costs for last 7 days
    - `/admin/users/guest/costs?from_date=2025-09-10&to_date=2025-09-10` - Guest costs for single date
    - `/admin/users/guest/costs?from_date=2025-09-08&to_date=2025-09-10` - Guest costs for date range

    **Note:** This endpoint aggregates costs for ALL guest users (without user_id) into a single summary.
    """
    try:
        return await service.get_guest_costs(from_date, to_date)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch guest costs: {str(e)}"
        ) from e
