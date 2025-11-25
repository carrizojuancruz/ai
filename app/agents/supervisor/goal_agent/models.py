from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Dict, List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    OFF_TRACK = "off_track"
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


# Data source types
class DataSource(str, Enum):
    LINKED_ACCOUNTS = "linked_accounts"
    MANUAL_INPUT = "manual_input"
    MIXED = "mixed"


# Plaid transaction categories for affected_categories
class PlaidCategory(str, Enum):
    INCOME = "INCOME"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    LOAN_PAYMENTS = "LOAN_PAYMENTS"
    BANK_FEES = "BANK_FEES"
    ENTERTAINMENT = "ENTERTAINMENT"
    FOOD_AND_DRINK = "FOOD_AND_DRINK"
    GENERAL_MERCHANDISE = "GENERAL_MERCHANDISE"
    HOME_IMPROVEMENT = "HOME_IMPROVEMENT"
    MEDICAL = "MEDICAL"
    PERSONAL_CARE = "PERSONAL_CARE"
    GENERAL_SERVICES = "GENERAL_SERVICES"
    GOVERNMENT_AND_NON_PROFIT = "GOVERNMENT_AND_NON_PROFIT"
    TRANSPORTATION = "TRANSPORTATION"
    TRAVEL = "TRAVEL"
    RENT_AND_UTILITIES = "RENT_AND_UTILITIES"
    MANUAL_EXPENSES = "MANUAL_EXPENSES"
    CASH_TRANSACTIONS = "CASH_TRANSACTIONS"
    CUSTOM_CATEGORY = "CUSTOM_CATEGORY"


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

    model_config = ConfigDict(use_enum_values=True)

    value: GoalCategory = Field(..., description="Goal category for routing")


# Goal nature
class GoalNatureInfo(BaseModel):
    """Defines the desired direction of change."""

    model_config = ConfigDict(use_enum_values=True)

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


# Evaluation configuration (single unified definition; keeps validator)
class EvaluationConfig(BaseModel):
    """Data source and evaluation configuration."""

    aggregation: AggregationMethod = Field(default=AggregationMethod.SUM)
    direction: EvaluationDirection = Field(default=EvaluationDirection.LESS_EQUAL)
    rounding: Decimal = Field(default=Decimal("0.01"), description="Quantize unit for rounding (e.g., Decimal('0.01') for 2 decimal places)")
    source: DataSource = Field(default=DataSource.MIXED)
    affected_categories: Optional[List[str]] = Field(default=None, description="Specific categories to consider")

    # Note: validation of affected_categories against PlaidCategory is conditional
    # and performed at the Goal model level (only for financial goals). We intentionally
    # avoid enforcing it here so non-financial goals can provide arbitrary taxonomy.
    pass


# Alerts system
class Thresholds(BaseModel):
    """Proactive engagement thresholds."""

    warn_progress_pct: Optional[Decimal] = Field(None, ge=0, le=100, description="Warning threshold percentage")
    alert_progress_pct: Optional[Decimal] = Field(None, ge=0, le=100, description="Critical alert threshold percentage")
    warn_days_remaining: Optional[int] = Field(None, ge=0, description="Days remaining for warning")


# Reminders system
class ReminderSchedule(BaseModel):
    """Schedule for a reminder. Minimal fields for recurring and one-time schedules."""

    # 'type' describes recurrence mode: 'one_time' or 'recurring'
    type: Literal["one_time", "recurring"] = Field(..., description="Schedule type")
    # Recurrence fields
    unit: Optional[Literal["day", "week", "month"]] = Field(
        None, description="Recurrence unit (day, week, month)"
    )
    every: int = Field(default=1, ge=1, description="Repeat interval (1 = every unit)")
    weekdays: Optional[List[Weekday]] = Field(
        None, description="Weekday list for weekly schedules (mon, tue, ... )"
    )
    month_day: Optional[int] = Field(None, description="Day of month for monthly schedules")
    start_date: Optional[datetime] = Field(None, description="Anchor/start date for the schedule")
    time_of_day: Optional[str] = Field(None, description="Time of day in 24h format HH:MM")


class ReminderItem(BaseModel):
    """Minimal reminder item for push notifications. Channel is assumed to be push.

    We intentionally omit runtime fields (ids, next_run, attempts) here — a worker can compute
    and persist runtime state elsewhere.
    """

    schedule: ReminderSchedule


class Reminders(BaseModel):
    """Reminders configuration container."""

    items: List[ReminderItem] = Field(default_factory=list)


# Status and progress
class GoalStatusInfo(BaseModel):
    """Current goal status."""

    model_config = ConfigDict(use_enum_values=True)

    value: GoalStatus = Field(default=GoalStatus.PENDING, description="Current status")


class Progress(BaseModel):
    """Current progress tracking."""

    current_value: Decimal = Field(default=Decimal("0"), description="Current value toward objective")
    percent_complete: Decimal = Field(default=Decimal("0"), ge=0, le=100, description="Completion percentage")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last progress update")


# Audit trail
class Audit(BaseModel):
    """Temporal traceability."""

    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


# Extend GoalCategory to include financial and non-financial types
class GoalKind(str, Enum):
    FINANCIAL_HABIT = "financial_habit"
    FINANCIAL_PUNCTUAL = "financial_punctual"
    NONFIN_HABIT = "nonfin_habit"
    NONFIN_PUNCTUAL = "nonfin_punctual"


# Cadence (single unified definition with window helpers)
class Cadence(BaseModel):
    days: int = Field(..., ge=1, description="Number of days in the cadence window")
    last_reset: Optional[datetime] = Field(None, description="Timestamp of the last reset")

    def roll_window_if_needed(self, current_time: datetime) -> bool:
        """Roll the cadence window if the current time exceeds the cadence duration."""
        if not self.last_reset or (current_time - self.last_reset).days >= self.days:
            self.last_reset = current_time
            return True
        return False

    def current_window_start(self) -> Optional[datetime]:
        return self.last_reset


# Notification config (single unified definition; window anti-dup + status gating)
class NotificationConfig(BaseModel):
    # Whether notifications are enabled/paused for this goal. Required field (no default).
    enabled: bool = Field(..., description="Whether notifications are enabled for this goal")
    status: bool = Field(default=False, description="Whether a pending notification exists")
    last_notified_at: Optional[datetime] = Field(None, description="Timestamp of the last notification")
    min_gap_hours: int = Field(default=24, ge=1, description="Minimum gap between notifications in hours")
    last_notified_window_start: Optional[datetime] = Field(
        None, description="Cadence window start at which we last notified"
    )

    def can_notify_now(self, current_time: datetime) -> bool:
        # If notifications are disabled, never notify
        if not self.enabled:
            return False
        if not self.last_notified_at:
            return True
        elapsed_hours = (current_time - self.last_notified_at).total_seconds() / 3600
        return elapsed_hours >= self.min_gap_hours

    def can_notify_in_window(self, window_start: Optional[datetime], now: datetime) -> bool:
        # If notifications are disabled, do not notify
        if not self.enabled:
            return False
        # 1) If a notification is pending, don't emit another
        if self.status:
            return False
        # 2) Anti-dup per cadence window
        if window_start is not None and self.last_notified_window_start == window_start:
            return False
        # 3) Anti-spam temporal gap
        return self.can_notify_now(now)

    def mark_notified_in_window(self, window_start: Optional[datetime], now: datetime):
        self.last_notified_at = now
        if window_start is not None:
            self.last_notified_window_start = window_start
        # Mark as pending until ack is processed downstream
        self.status = True


# === BACKWARD COMPATIBLE ADDITIONS ===

# 1) State per cadence window (for Current/Previous + streaks + counters)
class WindowState(BaseModel):
    current_accomplished: bool = False                      # CurrentState.IsAccomplished
    previous_accomplished: Optional[bool] = None            # PreviousState.IsAccomplished
    recurrent_progress: Decimal = Decimal("0")              # RecurrentProgressCounter (per window)
    total_progress: Decimal = Decimal("0")                  # TotalProgressCounter (lifetime)
    streak_count: int = 0                                   # streaks of accomplished windows
    nudge_level: int = 0                                    # dynamic nudge intensity (increases on failure)
    last_window_started_at: Optional[datetime] = None       # start of active window (for anti-dup)

    def roll_for_new_window(self, window_start: datetime):
        # Shift state: current -> previous, reset recurrent and set new start
        self.previous_accomplished = self.current_accomplished
        self.current_accomplished = False
        self.recurrent_progress = Decimal("0")
        self.last_window_started_at = window_start


# === GOAL (with non-disruptive additions) ===
class Goal(BaseModel):
    """Goals System V2 – 100% coverage doc, backward compatible with V1."""

    # Core
    goal_id: Optional[UUID] = Field(default=None, description="Unique goal identifier")
    user_id: UUID = Field(..., description="User identifier")
    version: Optional[int] = Field(default=1, description="Version for optimistic concurrency")

    # Original definition
    goal: GoalBase = Field(..., description="Goal title and description")
    category: GoalCategoryInfo = Field(..., description="Goal category for routing")
    nature: GoalNatureInfo = Field(..., description="Desired direction of change")
    frequency: Frequency = Field(..., description="Evaluation calendar")
    amount: Amount = Field(..., description="Quantitative target")

    # NEW: goal type (Financial/Non-Fin × Habit/Punctual)
    kind: GoalKind = Field(..., description="financial/nonfin × habit/punctual")

    # NEW: optional non-financial taxonomy (for non-financial habits)
    nonfin_category: Optional[str] = Field(
        None, description="Non-financial category (AI-assigned taxonomy)"
    )

    # Evaluation (reactivated)
    evaluation: EvaluationConfig = Field(
        default_factory=EvaluationConfig, description="Evaluation configuration"
    )

    # Thresholds & reminders (unchanged)
    thresholds: Optional[Thresholds] = Field(None, description="Alert thresholds")
    reminders: Optional[Reminders] = Field(None, description="Reminder configuration")

    # Status & progress (kept) + cadence-scoped state (new)
    status: GoalStatusInfo = Field(default=GoalStatusInfo(), description="Current status")
    progress: Progress = Field(default_factory=Progress, description="Current progress")
    state: WindowState = Field(default_factory=WindowState, description="Cadence-scoped state")

    # Metadata / audit (kept)
    metadata: Optional[dict[str, str]] = Field(None, description="Additional metadata")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key for creation")
    audit: Optional[Audit] = Field(None, description="Creation and update timestamps")

    # Cadence & notifications (kept + extended)
    notifications_enabled: bool = Field(default=True, description="Enable notifications")
    cadence: Optional[Cadence] = Field(None, description="Cadence configuration for recurring goals")
    notifications: Optional[NotificationConfig] = Field(None, description="Notification configuration")

    # NEW: open-ended / end-defined signals at goal level (for punctual goals)
    end_date: Optional[datetime] = Field(None, description="Optional final date for punctual or time-bound goals")
    no_end_date: bool = Field(default=False, description="Open-ended goal without a defined end date")

    # === Helper methods (backward compatible) ===

    def evaluate_window_rollover(self, now: datetime) -> bool:
        """Sync cadence window: if it rolls, update WindowState."""
        if not self.cadence:
            return False
        rolled = self.cadence.roll_window_if_needed(now)
        if rolled:
            # If the window that just closed was not accomplished, increase nudge intensity
            if self.state.current_accomplished is False:
                self.state.nudge_level += 1
            # Roll state and set new window start
            self.state.roll_for_new_window(self.cadence.current_window_start())
        elif self.state.last_window_started_at is None and self.cadence.current_window_start():
            # Initialize first window if missing
            self.state.last_window_started_at = self.cadence.current_window_start()
        return rolled

    def register_progress(self, delta: Decimal, now: datetime):
        """Apply progress to both lifetime total and current window's recurrent counter.

        Keep percent_complete if you already compute it elsewhere.
        """
        self.state.recurrent_progress += delta
        self.state.total_progress += delta
        self.progress.current_value += delta
        self.progress.updated_at = now

    def set_accomplished(self, accomplished: bool):
        """Mark current window accomplishment and adjust streak & nudge intensity.

        - If accomplished turns True: increase streak (reset to 1 if previous False) and reduce nudge.
        - If it flips from True to False within the window: raise nudge level.
        """
        if accomplished and not self.state.current_accomplished:
            self.state.current_accomplished = True
            self.state.streak_count = (self.state.streak_count + 1) if (self.state.previous_accomplished is True) else 1
            self.state.nudge_level = max(0, self.state.nudge_level - 1)
        elif not accomplished and self.state.current_accomplished:
            self.state.current_accomplished = False
            self.state.nudge_level += 1

    def can_send_nudge(self, now: datetime) -> bool:
        """Respect temporal anti-spam and per-window anti-duplication, and honor NotificationStatus."""
        if not self.notifications:
            return False
        # If a notification is pending, do not emit another
        if self.notifications.status:
            return False
        window_start = self.cadence.current_window_start() if self.cadence else None
        return self.notifications.can_notify_in_window(window_start, now)

    def mark_nudged(self, now: datetime):
        if not self.notifications:
            return
        window_start = self.cadence.current_window_start() if self.cadence else None
        self.notifications.mark_notified_in_window(window_start, now)

    @model_validator(mode="after")
    def _validate_financial_affected_categories(self) -> "Goal":
        """If the goal is financial, enforce that evaluation.affected_categories contains only allowed Plaid categories.

        For financial goals the field is required and must be a subset of ALLOWED_CATEGORIES.
        """
        if self.kind in (GoalKind.FINANCIAL_HABIT, GoalKind.FINANCIAL_PUNCTUAL):
            v = None
            try:
                v = self.evaluation.affected_categories
            except Exception:
                v = None

            # Require presence for financial goals
            if not v:
                allowed = ", ".join(sorted(ALLOWED_CATEGORIES))
                raise ValueError(
                    "evaluation.affected_categories is required for financial goals. "
                    f"Allowed categories are: {allowed}"
                )

            # Validate values
            invalid = [c for c in v if c not in ALLOWED_CATEGORIES]
            if invalid:
                allowed = ", ".join(sorted(ALLOWED_CATEGORIES))
                raise ValueError(
                    f"Invalid affected_categories: {invalid}. Allowed categories are: {allowed}"
                )

        return self

    @model_validator(mode="after")
    def _validate_habit_frequency(self) -> "Goal":
        """For habit goals (financial_habit, nonfin_habit), require recurrent frequency with unit in [day, week, month]."""
        if self.kind in (GoalKind.FINANCIAL_HABIT, GoalKind.NONFIN_HABIT):
            if self.frequency.type != "recurrent":
                raise ValueError("Habit goals must have recurrent frequency.")
            if not self.frequency.recurrent:
                raise ValueError("Recurrent frequency details are required for habit goals.")
            allowed_units = {"day", "week", "month"}
            if self.frequency.recurrent.unit not in allowed_units:
                raise ValueError(f"Invalid frequency unit for habit goals. Allowed: {', '.join(allowed_units)}")
        return self

    @model_validator(mode="after")
    def _validate_date_range(self) -> "Goal":
        """Validate that start_date is not after end_date for recurrent frequency goals."""
        if self.frequency.type == "recurrent" and self.frequency.recurrent:
            start_date = self.frequency.recurrent.start_date
            end_date = self.frequency.recurrent.end_date

            if start_date and end_date and start_date > end_date:
                raise ValueError(
                    "Invalid date range: start date cannot be after end date. "
                    "Please provide a valid date range where the start date comes before the end date."
                )
        return self
