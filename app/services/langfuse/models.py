from datetime import date
from typing import List, Optional

from pydantic import BaseModel


class UserCostSummary(BaseModel):
    user_id: Optional[str] = None
    date: date
    total_cost: float = 0.0
    total_tokens: int = 0
    trace_count: int = 0


class AdminCostSummary(BaseModel):
    """Admin cost summary with only essential fields."""

    user_id: Optional[str] = None
    total_cost: float = 0.0
    trace_count: int = 0


class GuestCostSummary(BaseModel):
    """Guest cost summary with core fields: total_cost and trace_count."""

    total_cost: float = 0.0
    trace_count: int = 0


class DailyCostFields(BaseModel):
    """Daily cost response with core fields: total_cost, trace_count, and date."""

    total_cost: float
    trace_count: int
    date: str  # Single date as string (YYYY-MM-DD)


class UserDailyCost(BaseModel):
    """User daily cost with user_id, date, total_cost, and trace_count."""

    user_id: str
    date: str  # Single date as string (YYYY-MM-DD)
    total_cost: float
    trace_count: int


class UserDailyCosts(BaseModel):
    """User with their daily costs grouped together."""

    user_id: str
    daily_costs: List[DailyCostFields]
