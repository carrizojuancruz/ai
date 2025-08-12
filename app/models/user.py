"""User context and preferences data models."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SubscriptionTier(str, Enum):
    """User subscription tiers as defined in the architecture."""

    GUEST = "guest"
    FREE = "free"
    PAID = "paid"


class UserContext(BaseModel):
    """Structured user context stored in PostgreSQL."""

    user_id: UUID = Field(default_factory=uuid4)
    email: str | None = None
    preferred_name: str | None = None
    pronouns: str | None = None
    language: str = Field(default="en-US")
    tone_preference: str | None = None

    city: str | None = None
    dependents: int | None = None

    income_band: str | None = None
    rent_mortgage: float | None = None
    primary_financial_goal: str | None = None

    subscription_tier: SubscriptionTier = SubscriptionTier.FREE
    social_signals_consent: bool = False
    ready_for_orchestrator: bool = False

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserPreferences(BaseModel):
    """User preferences and settings."""

    user_id: UUID
    notification_enabled: bool = True
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    max_nudges_per_day: int = 3
    max_nudges_per_week: int = 10
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
