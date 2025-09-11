"""Admin routes for cost analytics - Essential endpoints only."""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.services.langfuse import LangfuseCostService
from app.services.langfuse.models import AdminCostSummary, UserDailyCosts, GuestCostSummary

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


# Dependency
def get_cost_service() -> LangfuseCostService:
    """Dependency to get cost service instance."""
    return LangfuseCostService()


@router.get("/total-costs", response_model=List[AdminCostSummary])
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


@router.get("/daily-costs", response_model=List[UserDailyCosts])
async def get_all_users_daily_costs_grouped(
    user_id: Optional[str] = Query(None, description="Filter by specific user ID (optional)"),  # noqa: B008
    from_date: Optional[date] = Query(None, description="Start date for range (YYYY-MM-DD)"),  # noqa: B008
    to_date: Optional[date] = Query(None, description="End date for range (YYYY-MM-DD)"),  # noqa: B008
    service: LangfuseCostService = Depends(get_cost_service)  # noqa: B008
) -> List[UserDailyCosts]:
    """Get daily costs for all users or a specific user, grouped by user.

    **Returns Structure B: List of users with their daily costs grouped together.**

    **Flexible Filtering:**
    - No user_id: Returns daily costs for ALL users
    - With user_id: Returns daily costs for SPECIFIC user only

    **Date Range Logic:**
    - No params: Last 30 days (from 30 days ago to today)
    - from_date only: From that date to today
    - to_date only: From that date to that date (single day)
    - Both dates: From from_date to to_date

    **Parameters:**
    - user_id: Optional. Filter by specific user ID
    - from_date: Optional. Start date in YYYY-MM-DD format
    - to_date: Optional. End date in YYYY-MM-DD format

    **Examples:**
    - /admin/users/daily-costs - Last 30 days for all users
    - /admin/users/daily-costs?user_id=abc123 - Last 30 days for specific user
    - /admin/users/daily-costs?user_id=abc123&from_date=2025-09-08 - From Sept 8 to today for specific user
    """
    try:
        return await service.get_all_users_daily_costs_grouped(from_date, to_date, user_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch grouped daily costs: {str(e)}"
        ) from e


@router.get("/guest/costs", response_model=GuestCostSummary)
async def get_guest_costs(
    from_date: Optional[date] = Query(None, description="Start date for range (YYYY-MM-DD)"),  # noqa: B008
    to_date: Optional[date] = Query(None, description="End date for range (YYYY-MM-DD)"),  # noqa: B008
    service: LangfuseCostService = Depends(get_cost_service)  # noqa: B008
) -> GuestCostSummary:
    """Get costs for guest users with core fields only: total_cost and trace_count.

    **Returns only essential fields:**
    - total_cost: The total cost for guest users
    - trace_count: The number of traces for guest users

    **Date Range Logic:**
    - **No params**: Last 30 days (from 30 days ago to today)
    - **from_date only**: From that date to today
    - **to_date only**: From that date to that date (single day)
    - **Both dates**: From from_date to to_date

    **Examples:**
    - `/admin/users/guest/costs` - Guest costs for last 30 days
    - `/admin/users/guest/costs?from_date=2025-09-10&to_date=2025-09-10` - Guest costs for single date
    - `/admin/users/guest/costs?from_date=2025-09-08&to_date=2025-09-10` - Guest costs for date range

    **Note:** This endpoint aggregates costs for ALL guest users (without user_id) into a single summary.
    """
    try:
        return await service.get_guest_costs_simple(from_date, to_date)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch guest costs: {str(e)}"
        ) from e
