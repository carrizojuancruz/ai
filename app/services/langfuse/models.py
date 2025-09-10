from datetime import date
from typing import Dict, Optional

from pydantic import BaseModel


class UserCostSummary(BaseModel):
    user_id: Optional[str] = None
    date: date
    total_cost: float = 0.0
    total_tokens: int = 0
    trace_count: int = 0


class CostSummary(BaseModel):
    """Aggregated cost summary across time periods."""

    user_id: Optional[str] = None
    total_cost: float = 0.0
    total_tokens: int = 0
    trace_count: int = 0
    date_range: Optional[Dict[str, str]] = None  # {"from": "2025-01-01", "to": "2025-12-31"}


class DailyCostResponse(BaseModel):
    """Response model for daily cost data with a single date field."""

    user_id: str
    total_cost: float
    total_tokens: int
    trace_count: int
    date: str  # Single date as string (YYYY-MM-DD)
