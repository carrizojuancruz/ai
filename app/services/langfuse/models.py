from datetime import date
from typing import Optional

from pydantic import BaseModel


class UserCostSummary(BaseModel):
    user_id: Optional[str] = None
    date: date
    total_cost: float = 0.0
    total_tokens: int = 0
    trace_count: int = 0
