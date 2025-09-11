"""Admin routes for cost analytics - Essential endpoints only."""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.services.langfuse import LangfuseCostService
from app.services.langfuse.models import AdminCostSummary, GuestCostSummary, UserDailyCosts

router = APIRouter(prefix="/admin/users", tags=["admin-users"])

USER_ID_QUERY = Query(None, description="Filter by specific user ID (optional)")
FROM_DATE_QUERY = Query(None, description="Start date for range (YYYY-MM-DD)")
TO_DATE_QUERY = Query(None, description="End date for range (YYYY-MM-DD)")


def get_cost_service() -> LangfuseCostService:
    """Dependency to get singleton cost service instance."""
    return LangfuseCostService.get_instance()


COST_SERVICE_DEPENDENCY = Depends(get_cost_service)


@router.get("/total-costs", response_model=List[AdminCostSummary])
async def get_user_costs(
    user_id: Optional[str] = USER_ID_QUERY,
    from_date: Optional[date] = FROM_DATE_QUERY,
    to_date: Optional[date] = TO_DATE_QUERY,
    service: LangfuseCostService = COST_SERVICE_DEPENDENCY
) -> List[AdminCostSummary]:
    """Get aggregated costs for registered users with essential fields: user_id, total_cost, trace_count.

    **Date Range Logic:**
    - No params: Last 30 days for all users
    - user_id only: Last 30 days for specific user
    - from_date only: From that date to today
    - Both dates: From from_date to to_date

    **Examples:**
    - `/admin/users/total-costs` - All users last 30 days
    - `/admin/users/total-costs?user_id=abc123` - Specific user last 30 days
    - `/admin/users/total-costs?from_date=2025-09-10&to_date=2025-09-10` - All users single date
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
    user_id: Optional[str] = USER_ID_QUERY,
    from_date: Optional[date] = FROM_DATE_QUERY,
    to_date: Optional[date] = TO_DATE_QUERY,
    service: LangfuseCostService = COST_SERVICE_DEPENDENCY
) -> List[UserDailyCosts]:
    """Get daily costs for all users or a specific user, grouped by user.

    **Date Range Logic:**
    - No params: Last 30 days for all users
    - user_id only: Last 30 days for specific user
    - from_date only: From that date to today
    - Both dates: From from_date to to_date

    **Examples:**
    - `/admin/users/daily-costs` - Last 30 days for all users
    - `/admin/users/daily-costs?user_id=abc123` - Last 30 days for specific user
    - `/admin/users/daily-costs?from_date=2025-09-08&to_date=2025-09-10` - Date range for all users
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
    from_date: Optional[date] = FROM_DATE_QUERY,
    to_date: Optional[date] = TO_DATE_QUERY,
    service: LangfuseCostService = COST_SERVICE_DEPENDENCY
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
        return await service.get_guest_costs(from_date, to_date)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch guest costs: {str(e)}"
        ) from e
