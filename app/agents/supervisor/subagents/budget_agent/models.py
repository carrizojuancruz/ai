"""
Models for the Budget Agent
"""

from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, ValidationError, field_validator, model_validator
from typing import Annotated

class Category(str, Enum):
    """
    Category of a budget.
    """
    DINING = "dining"
    GROCERIES = "groceries"
    HOUSING = "housing"
    TRANSPORT = "transport"
    ENTERTAINMENT = "entertainment"
    HEALTHCARE = "healthcare"
    UTILITIES = "utilities"
    EDUCATION = "education"
    TRAVEL = "travel"
    OTHER = "other"

ALLOWED_CATEGORIES: set[str] = {c.value for c in Category}


class CategoryLimit(BaseModel):
    """
    Category limit for a budget.
    """
    amount: Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
    hard_cap: bool = True
    alert_thresholds: Optional[List[Decimal]] = None
    notes: Optional[str] = None


class BudgetStatus(str, Enum):
    """
    Status of a budget.
    """
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"

class Budget(BaseModel):
    """
    +-   **High-Level Schemas:**
    -   **`budgets` table (mutable, standardized schema with version/audit):**
        -   `budget_id` (Primary Key, UUID)
        -   `user_id` (Foreign Key to `users`)
        -   `version` (INT) – increments on update to preserve history
        -   `budget_name` (VARCHAR)
        -   `category_limits` (JSONB) - e.g., `{ "dining": 500, "groceries": 800 }`
        -   `since`(TIMESTAMP)
        -   `until`(TIMESTAMP)
        -   `is_active` (BOOLEAN)
        -   `created_at` (TIMESTAMP)
        -   `updated_at` (TIMESTAMP)
    """
    model_config = ConfigDict(populate_by_name=True)

    budget_id: Optional[UUID] = Field(default=None)
    user_id: UUID
    version: Optional[int] = Field(default=1)
    budget_name: str
    category_limits: Dict[str, CategoryLimit]
    since: datetime
    until: datetime

    # Lifecycle
    is_active: bool = Field(default=True)
    status: BudgetStatus = Field(default=BudgetStatus.ACTIVE)

    # Money/Locale
    currency_code: str = Field(default="USD")
    timezone: Optional[str] = None

    # Traceability / Extensibility
    schema_version: int = Field(default=1)
    metadata: Optional[Dict[str, str]] = None
    idempotency_key: Optional[str] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("category_limits")
    @classmethod
    def _validate_categories(cls, v: Dict[str, CategoryLimit]) -> Dict[str, CategoryLimit]:
        unknown = [k for k in v.keys() if k not in ALLOWED_CATEGORIES]
        if unknown:
            raise ValidationError(
                [
                    {
                        "type": "value_error.category_not_allowed",
                        "loc": ("category_limits",),
                        "msg": f"Unknown categories: {', '.join(unknown)}",
                        "input": v,
                    }
                ],
                cls,
            )
        return v

    @model_validator(mode="after")
    def _validate_dates_and_status(self) -> "Budget":
        if self.until <= self.since:
            raise ValidationError(
                [
                    {
                        "type": "value_error.dates",
                        "loc": ("until",),
                        "msg": "`until` must be greater than `since`",
                        "input": self.until,
                    }
                ],
                type(self),
            )
        # Keep is_active and status consistent
        if self.status == BudgetStatus.ACTIVE and not self.is_active:
            self.status = BudgetStatus.INACTIVE
        elif self.status != BudgetStatus.ACTIVE and self.is_active:
            self.is_active = False
        return self