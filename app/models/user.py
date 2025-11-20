from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SubscriptionTier(str, Enum):
    GUEST = "guest"
    FREE = "free"
    PAID = "paid"


class Identity(BaseModel):
    preferred_name: str | None = None
    pronouns: str | None = None
    age: int | None = Field(default=None, ge=0)
    birth_date: str | None = None


class Safety(BaseModel):
    blocked_categories: list[str] = Field(default_factory=list)
    allow_sensitive: bool | None = None


class Style(BaseModel):
    tone: str | None = None
    verbosity: str | None = None
    formality: str | None = None
    emojis: str | None = None


class Location(BaseModel):
    city: str | None = None
    region: str | None = None
    cost_of_living: str | None = None
    travel: str | None = None
    local_rules: list[str] = Field(default_factory=list)


class LocaleInfo(BaseModel):
    language: str | None = None
    time_zone: str | None = None
    currency_code: str | None = None
    local_now_iso: str | None = None


class Accessibility(BaseModel):
    reading_level_hint: str | None = None
    glossary_level_hint: str | None = None


class BudgetPosture(BaseModel):
    active_budget: bool = False
    current_month_spend_summary: str | None = None


class Household(BaseModel):
    dependents_count: int | None = Field(default=None, ge=0)
    household_size: int | None = Field(default=None, ge=1)
    pets: str | None = None


class UserContext(BaseModel):
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
    age: int | None = None
    age_range: str | None = None
    money_feelings: list[str] = Field(default_factory=list)
    housing_satisfaction: str | None = None
    health_insurance: str | None = None
    health_cost: str | None = None
    learning_interests: list[str] = Field(default_factory=list)
    expenses: list[str] = Field(default_factory=list)
    identity: Identity = Field(default_factory=Identity)
    safety: Safety = Field(default_factory=Safety)
    style: Style = Field(default_factory=Style)
    location: Location = Field(default_factory=Location)
    locale_info: LocaleInfo = Field(default_factory=LocaleInfo)
    goals: list[str] = Field(default_factory=list)
    income: str | None = None
    housing: str | None = None
    tier: str | None = None
    accessibility: Accessibility = Field(default_factory=Accessibility)
    budget_posture: BudgetPosture = Field(default_factory=BudgetPosture)
    household: Household = Field(default_factory=Household)
    assets_high_level: list[str] = Field(default_factory=list)
    blocked_topics: list[str] | None = Field(default=None)
    personal_information: str | None = Field(default=None)

    def sync_flat_to_nested(self) -> None:
        if self.preferred_name:
            self.identity.preferred_name = self.preferred_name
        if self.pronouns:
            self.identity.pronouns = self.pronouns
        if self.age is not None:
            self.identity.age = self.age
        if self.tone_preference:
            self.style.tone = self.tone_preference
        if self.city:
            self.location.city = self.city
        if self.dependents is not None:
            self.household.dependents_count = self.dependents
        if self.language:
            self.locale_info.language = self.language
        if self.primary_financial_goal and self.primary_financial_goal not in self.goals:
            self.goals.append(self.primary_financial_goal)
        if self.social_signals_consent:
            pass

    def sync_nested_to_flat(self) -> None:
        if self.identity.preferred_name:
            self.preferred_name = self.identity.preferred_name
        if self.identity.pronouns:
            self.pronouns = self.identity.pronouns
        if self.identity.age is not None:
            self.age = self.identity.age
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
    user_id: UUID
    notification_enabled: bool = True
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    max_nudges_per_day: int = 3
    max_nudges_per_week: int = 10
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
