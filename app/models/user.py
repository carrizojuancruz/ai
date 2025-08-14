"""User context and preferences data models."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SubscriptionTier(str, Enum):
    """User subscription tiers as defined in the architecture."""

    GUEST = "guest"
    FREE = "free"
    PAID = "paid"


class Identity(BaseModel):
    preferred_name: Optional[str] = None
    pronouns: Optional[str] = None
    age: Optional[int] = Field(default=None, ge=0)


class Safety(BaseModel):
    blocked_categories: list[str] = Field(default_factory=list)
    allow_sensitive: Optional[bool] = None


class Style(BaseModel):
    tone: Optional[str] = None
    verbosity: Optional[str] = None
    formality: Optional[str] = None
    emojis: Optional[str] = None


class Location(BaseModel):
    city: Optional[str] = None
    region: Optional[str] = None
    cost_of_living: Optional[str] = None
    travel: Optional[str] = None
    local_rules: list[str] = Field(default_factory=list)


class LocaleInfo(BaseModel):
    language: Optional[str] = None
    time_zone: Optional[str] = None
    currency_code: Optional[str] = None
    local_now_iso: Optional[str] = None


class Accessibility(BaseModel):
    reading_level_hint: Optional[str] = None
    glossary_level_hint: Optional[str] = None


class BudgetPosture(BaseModel):
    active_budget: bool = False
    current_month_spend_summary: Optional[str] = None


class Household(BaseModel):
    dependents_count: Optional[int] = Field(default=None, ge=0)
    household_size: Optional[int] = Field(default=None, ge=1)
    pets: Optional[str] = (
        None  # none|dog|cat|dog_and_cat|other_small_animals|multiple_varied
    )


class UserContext(BaseModel):
    """Structured user context stored in PostgreSQL (later) and injected in prompts."""

    user_id: UUID = Field(default_factory=uuid4)
    email: Optional[str] = None
    preferred_name: Optional[str] = None
    pronouns: Optional[str] = None
    language: str = Field(default="en-US")
    tone_preference: Optional[str] = None
    city: Optional[str] = None
    dependents: Optional[int] = None
    income_band: Optional[str] = None
    rent_mortgage: Optional[float] = None
    primary_financial_goal: Optional[str] = None
    subscription_tier: SubscriptionTier = SubscriptionTier.FREE
    social_signals_consent: bool = False
    ready_for_orchestrator: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    identity: Identity = Field(default_factory=Identity)
    safety: Safety = Field(default_factory=Safety)
    style: Style = Field(default_factory=Style)
    location: Location = Field(default_factory=Location)
    locale_info: LocaleInfo = Field(default_factory=LocaleInfo)
    goals: list[str] = Field(default_factory=list)
    income: Optional[str] = None  # low|lower_middle|middle|upper_middle|high|very_high
    housing: Optional[str] = (
        None  # own_home|rent|mortgage|living_with_family|temporary|homeless
    )
    tier: Optional[str] = None  # free|basic|premium|enterprise
    accessibility: Accessibility = Field(default_factory=Accessibility)
    budget_posture: BudgetPosture = Field(default_factory=BudgetPosture)
    household: Household = Field(default_factory=Household)
    assets_high_level: list[str] = Field(default_factory=list)

    def sync_flat_to_nested(self) -> None:
        if self.preferred_name:
            self.identity.preferred_name = self.preferred_name
        if self.pronouns:
            self.identity.pronouns = self.pronouns
        if self.tone_preference:
            self.style.tone = self.tone_preference
        if self.city:
            self.location.city = self.city
        if self.dependents is not None:
            self.household.dependents_count = self.dependents
        if self.language:
            self.locale_info.language = self.language
        if (
            self.primary_financial_goal
            and self.primary_financial_goal not in self.goals
        ):
            self.goals.append(self.primary_financial_goal)
        if self.social_signals_consent:
            # Map to proactivity: represented via budget_posture or separate flag in future
            pass

    def sync_nested_to_flat(self) -> None:
        if self.identity.preferred_name:
            self.preferred_name = self.identity.preferred_name
        if self.identity.pronouns:
            self.pronouns = self.identity.pronouns
        if self.style.tone:
            self.tone_preference = self.style.tone
        if self.location.city:
            self.city = self.location.city
        if self.household.dependents_count is not None:
            self.dependents = self.household.dependents_count
        if self.locale_info.language:
            self.language = self.locale_info.language
        if self.goals and not self.primary_financial_goal:
            self.primary_financial_goal = self.goals[0]


class UserPreferences(BaseModel):
    """User preferences and settings."""

    user_id: UUID
    notification_enabled: bool = True
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    max_nudges_per_day: int = 3
    max_nudges_per_week: int = 10
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
