"""
Models for the Goal Agent (Goals System V1)
"""

from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Union
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, ValidationError, field_validator, model_validator
from typing import Annotated

# Goal Categories for intelligent routing to specialized agents
class GoalCategory(str, Enum):
    SAVING = "saving"
    SPENDING = "spending"
    DEBT = "debt"
    INCOME = "income"
    INVESTMENT = "investment"
    NET_WORTH = "net_worth"
    OTHER = "other"

# Goal Nature defines the desired direction of change
class GoalNature(str, Enum):
    INCREASE = "increase"
    REDUCE = "reduce"

# Goal Status with specific state transitions
class GoalStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ERROR = "error"
    DELETED = "deleted"

# Frequency types for goal evaluation
class FrequencyUnit(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"

class Weekday(str, Enum):
    MON = "mon"
    TUE = "tue"
    WED = "wed"
    THU = "thu"
    FRI = "fri"
    SAT = "sat"
    SUN = "sun"

# Amount types for goal targets
class AmountBasis(str, Enum):
    INCOME = "income"
    SPENDING = "spending"
    CATEGORY = "category"
    ACCOUNT = "account"
    NET_WORTH = "net_worth"
    CUSTOM_QUERY = "custom_query"

# Aggregation methods for goal evaluation
class AggregationMethod(str, Enum):
    SUM = "sum"
    AVERAGE = "average"
    MAX = "max"
    MIN = "min"

# Direction for goal evaluation
class EvaluationDirection(str, Enum):
    GREATER_EQUAL = "≥"
    LESS_EQUAL = "≤"
    EQUAL = "="

# Rounding methods
class RoundingMethod(str, Enum):
    NONE = "none"
    FLOOR = "floor"
    CEIL = "ceil"
    ROUND = "round"

# Data source types
class DataSource(str, Enum):
    LINKED_ACCOUNTS = "linked_accounts"
    MANUAL_INPUT = "manual_input"
    MIXED = "mixed"

# Plaid transaction categories for affected_categories
class PlaidCategory(str, Enum):
    BANK_FEES = "bank_fees"
    HOME_IMPROVEMENT = "home_improvement"
    RENT_UTILITIES = "rent_utilities"
    ENTERTAINMENT = "entertainment"
    INCOME = "income"
    TRANSFER_IN = "transfer_in"
    FOOD_DRINK = "food_drink"
    LOAN_PAYMENTS = "loan_payments"
    TRANSFER_OUT = "transfer_out"
    GENERAL_MERCHANDISE = "general_merchandise"
    MEDICAL = "medical"
    TRANSPORTATION = "transportation"
    GENERAL_SERVICES = "general_services"
    PERSONAL_CARE = "personal_care"
    TRAVEL = "travel"
    GOVERNMENT_NON_PROFIT = "government_non_profit"
    MANUAL_EXPENSES = "manual_expenses"
    CASH_TRANSACTIONS = "cash_transactions"
    CUSTOM_CATEGORY = "custom_category"

ALLOWED_CATEGORIES: set[str] = {c.value for c in PlaidCategory}

# Money type with validation
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]

# Base goal structure
class GoalBase(BaseModel):
    """Base goal structure for human identification and context."""
    title: str = Field(..., description="Descriptive title of the objective")
    description: Optional[str] = Field(None, description="Optional detailed description")

# Category classification
class GoalCategoryInfo(BaseModel):
    """Classification of the objective for intelligent routing."""
    value: GoalCategory = Field(..., description="Goal category for routing")

# Goal nature
class GoalNatureInfo(BaseModel):
    """Defines the desired direction of change."""
    value: GoalNature = Field(..., description="Desired direction: increase or reduce")

# Frequency structures
class SpecificFrequency(BaseModel):
    """Specific date frequency."""
    date: datetime = Field(..., description="Single target date")

class RecurrentFrequency(BaseModel):
    """Recurring frequency with temporal anchors."""
    unit: FrequencyUnit = Field(..., description="Time unit")
    every: int = Field(..., ge=1, description="Every X units")
    start_date: datetime = Field(..., description="Start date")
    end_date: Optional[datetime] = Field(None, description="Optional end date")
    anchors: Optional[Dict[str, Union[int, str]]] = Field(None, description="Temporal anchors")

class Frequency(BaseModel):
    """Goal evaluation calendar."""
    type: str = Field(..., description="Frequency type")
    specific: Optional[SpecificFrequency] = None
    recurrent: Optional[RecurrentFrequency] = None

# Amount structures
class AbsoluteAmount(BaseModel):
    """Absolute amount target."""
    currency: str = Field(default="USD", description="ISO 4217 currency code")
    target: Money = Field(..., description="Target value")

class PercentageAmount(BaseModel):
    """Percentage-based target."""
    target_pct: Decimal = Field(..., ge=0, le=100, description="Target percentage 0-100")
    of: Dict[str, Union[str, Optional[str]]] = Field(..., description="Percentage basis and reference")

class Amount(BaseModel):
    """Quantitative target definition."""
    type: str = Field(..., description="Amount type")
    absolute: Optional[AbsoluteAmount] = None
    percentage: Optional[PercentageAmount] = None

# Evaluation configuration
class EvaluationConfig(BaseModel):
    """Data source and evaluation configuration."""
    aggregation: AggregationMethod = Field(default=AggregationMethod.SUM)
    direction: EvaluationDirection = Field(default=EvaluationDirection.LESS_EQUAL)
    rounding: Optional[RoundingMethod] = Field(default=RoundingMethod.NONE)
    source: DataSource = Field(default=DataSource.MIXED)
    affected_categories: Optional[List[str]] = Field(default=None, description="Specific categories to consider")

    @field_validator("affected_categories")
    @classmethod
    def _validate_categories(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None:
            unknown = [k for k in v if k not in ALLOWED_CATEGORIES]
            if unknown:
                raise ValidationError(
                    [
                        {
                            "type": "value_error.category_not_allowed",
                            "loc": ("affected_categories",),
                            "msg": f"Unknown categories: {', '.join(unknown)}",
                            "input": v,
                        }
                    ],
                    cls,
                )
        return v

# Alerts system
class Thresholds(BaseModel):
    """Proactive engagement thresholds."""
    warn_progress_pct: Optional[Decimal] = Field(None, ge=0, le=100, description="Warning threshold percentage")
    alert_progress_pct: Optional[Decimal] = Field(None, ge=0, le=100, description="Critical alert threshold percentage")
    warn_days_remaining: Optional[int] = Field(None, ge=0, description="Days remaining for warning")

# Reminders system
class ReminderItem(BaseModel):
    """User-configurable reminder."""
    type: str = Field(..., description="Reminder type: push, email, sms")
    when: str = Field(..., description="Temporal expression")

class Reminders(BaseModel):
    """Reminders configuration."""
    items: List[ReminderItem] = Field(default_factory=list)

# Status and progress
class GoalStatusInfo(BaseModel):
    """Current goal status."""
    value: GoalStatus = Field(default=GoalStatus.PENDING, description="Current status")

class Progress(BaseModel):
    """Current progress tracking."""
    current_value: Optional[Decimal] = Field(None, description="Current value toward objective")
    percent_complete: Optional[Decimal] = Field(None, ge=0, le=100, description="Completion percentage")
    updated_at: Optional[datetime] = Field(None, description="Last progress update")

# Audit trail
class Audit(BaseModel):
    """Temporal traceability."""
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

# Main Goal model
class Goal(BaseModel):
    """
    Complete Goals System V1 specification.
    Enables users to define, track, and achieve financial objectives.
    """
    model_config = ConfigDict(populate_by_name=True)

    # Core identification
    goal_id: Optional[UUID] = Field(default=None, description="Unique goal identifier")
    user_id: UUID = Field(..., description="User identifier")
    version: Optional[int] = Field(default=1, description="Version for optimistic concurrency")

    # Goal definition
    goal: GoalBase = Field(..., description="Goal title and description")
    category: GoalCategoryInfo = Field(..., description="Goal category for routing")
    nature: GoalNatureInfo = Field(..., description="Desired direction of change")
    frequency: Frequency = Field(..., description="Evaluation calendar")
    amount: Amount = Field(..., description="Quantitative target")

    # Evaluation and tracking
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig, description="Evaluation configuration")
    thresholds: Optional[Thresholds] = Field(None, description="Alert thresholds")
    reminders: Optional[Reminders] = Field(None, description="Reminder configuration")

    # Status and progress
    status: GoalStatusInfo = Field(default=GoalStatusInfo(), description="Current status")
    progress: Optional[Progress] = Field(None, description="Current progress")

    # Metadata and extensibility
    metadata: Optional[Dict[str, str]] = Field(None, description="Additional metadata")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key for creation")

    # Audit trail
    audit: Optional[Audit] = Field(None, description="Creation and update timestamps")

    @model_validator(mode="after")
    def _validate_goal_configuration(self) -> "Goal":
        """Validate goal configuration consistency."""
        # Validate frequency type matches content
        freq_type = getattr(self.frequency, 'type', None)
        if freq_type == "specific" and not getattr(self.frequency, 'specific', None):
            raise ValidationError(
                [
                    {
                        "type": "value_error.frequency_mismatch",
                        "loc": ("frequency",),
                        "msg": "Specific frequency type requires specific date",
                        "input": self.frequency,
                    }
                ],
                type(self),
            )
        
        if freq_type == "recurrent" and not getattr(self.frequency, 'recurrent', None):
            raise ValidationError(
                [
                    {
                        "type": "value_error.frequency_mismatch",
                        "loc": ("frequency",),
                        "msg": "Recurrent frequency type requires recurrent configuration",
                        "input": self.frequency,
                    }
                ],
                type(self),
            )

        # Validate amount type matches content
        amount_type = getattr(self.amount, 'type', None)
        if amount_type == "absolute" and not getattr(self.amount, 'absolute', None):
            raise ValidationError(
                [
                    {
                        "type": "value_error.amount_mismatch",
                        "loc": ("amount",),
                        "msg": "Absolute amount type requires absolute configuration",
                        "input": self.amount,
                    }
                ],
                type(self),
            )
        
        if amount_type == "percentage" and not getattr(self.amount, 'percentage', None):
            raise ValidationError(
                [
                    {
                        "type": "value_error.amount_mismatch",
                        "loc": ("amount",),
                        "msg": "Percentage amount type requires percentage configuration",
                        "input": self.amount,
                    }
                ],
                type(self),
            )

        return self
