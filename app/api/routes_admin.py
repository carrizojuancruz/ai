"""Admin routes for cost analytics following REST API design principles."""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.langfuse import LangfuseCostService, UserCostSummary

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


# Response Models
class DailyCostSummary(BaseModel):
    """Daily cost summary for all users grouped by user."""

    date: date
    users: List[UserCostSummary] = Field(..., description="Individual user costs")
    total_cost: float = Field(..., description="Total cost across all users")
    total_users: int = Field(..., description="Number of users")
    guest_cost: float = Field(..., description="Total cost from guest users")
    registered_cost: float = Field(..., description="Total cost from registered users")


# Dependency
def get_cost_service() -> LangfuseCostService:
    """Dependency to get cost service instance."""
    return LangfuseCostService()


@router.get("/costs", response_model=List[UserCostSummary])
async def get_user_costs(
    date: Optional[date] = Query(None, description="Target date (YYYY-MM-DD), defaults to today"),  # noqa: B008
    user_id: Optional[str] = Query(None, description="Filter by specific user ID (optional)"),  # noqa: B008
    service: LangfuseCostService = Depends(get_cost_service)  # noqa: B008
) -> List[UserCostSummary]:
    """Get costs per user with smart defaults and flexible filtering.

    **Smart Parameter Handling:**
    - No params: All users for today
    - Only date: All users for specified date  
    - Only user_id: Specific user for today
    - Both: Specific user for specified date

    **Examples:**
    - `/admin/users/costs` - All users for today
    - `/admin/users/costs?date=2025-09-02` - All users for that date
    - `/admin/users/costs?user_id=abc123` - Specific user for today
    - `/admin/users/costs?date=2025-09-02&user_id=abc123` - Specific user for that date
    """
    from datetime import date as date_module
    
    # Use today as default if no date provided
    target_date = date if date is not None else date_module.today()
    
    try:
        return await service.get_costs_per_user_date(target_date, user_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch user costs: {str(e)}"
        ) from e


@router.get("/guest/costs", response_model=UserCostSummary)
async def get_guest_costs(
    date: date = Query(..., description="Target date (YYYY-MM-DD)"),  # noqa: B008
    service: LangfuseCostService = Depends(get_cost_service)  # noqa: B008
) -> UserCostSummary:
    """Get cost for guest users (anonymous/no user ID) on a specific date.

    **Endpoint 2: Get the cost per Guest user (no user id)/date**

    - **date**: Required. Target date in YYYY-MM-DD format
    - **Returns**: Aggregated cost summary for all anonymous users
    - **Source**: Guest Langfuse project (users without authentication)
    - **Features**: Handles traces with no user_id in metadata

    **Example:**
    - `/admin/users/guest/costs?date=2025-09-02` - Total guest costs for that date
    """
    try:
        return await service.get_guest_costs_per_date(date)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch guest costs: {str(e)}"
        ) from e


@router.get("/costs/daily", response_model=DailyCostSummary)
async def get_daily_costs_grouped_by_user(
    date: date = Query(..., description="Target date (YYYY-MM-DD)"),  # noqa: B008
    service: LangfuseCostService = Depends(get_cost_service)  # noqa: B008
) -> DailyCostSummary:
    """Get cost per date for every user (grouped by user).

    **Endpoint 3: Get Cost per date for every user (group by user)**

    - **date**: Required. Target date in YYYY-MM-DD format
    - **Returns**: Comprehensive cost breakdown for all users (registered + guest)
    - **Features**:
      - Combines both supervisor and guest Langfuse projects
      - Groups by individual user IDs from metadata
      - Provides summary statistics (totals, breakdowns)
      - Uses trace.total_cost directly from traces table

    **Example:**
    - `/admin/users/costs/daily?date=2025-09-02` - All users grouped with summary stats
    """
    try:
        # Get registered user costs
        registered_costs = await service.get_costs_per_user_date(date)

        # Get guest costs
        guest_costs = await service.get_guest_costs_per_date(date)

        # Combine all users
        all_users = registered_costs.copy()
        if guest_costs.total_cost > 0:  # Only include if there are actual guest costs
            all_users.append(guest_costs)

        # Calculate summary statistics
        total_cost = sum(user.total_cost for user in all_users)
        guest_cost = guest_costs.total_cost
        registered_cost = total_cost - guest_cost

        return DailyCostSummary(
            date=date,
            users=all_users,
            total_cost=total_cost,
            total_users=len(all_users),
            guest_cost=guest_cost,
            registered_cost=registered_cost
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch daily costs grouped by user: {str(e)}"
        ) from e
