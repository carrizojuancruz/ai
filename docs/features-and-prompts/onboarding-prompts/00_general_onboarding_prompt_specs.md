# 00_General_Onboarding_Prompt.md

This is the master prompt that defines the overall tone, approach, and guidelines for Vera's onboarding process. This prompt should be used by the LLM across all conversational nodes (01-10).

---

## [Final Output Format]

After completing the onboarding conversation, compile responses into this structured format:

```json
class SubscriptionTier(str, Enum):
    """User subscription tiers as defined in the architecture."""

    GUEST = "guest"
    FREE = "free"
    PAID = "paid"


class Identity(BaseModel):
    preferred_name: str | None = None
    pronouns: str | None = None
    age: int | None = Field(default=None, ge=0)


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
    pets: str | None = (
        None  # none|dog|cat|dog_and_cat|other_small_animals|multiple_varied
    )


class UserContext(BaseModel):
    """Structured user context stored in PostgreSQL (later) and injected in prompts."""

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

    identity: Identity = Field(default_factory=Identity)
    safety: Safety = Field(default_factory=Safety)
    style: Style = Field(default_factory=Style)
    location: Location = Field(default_factory=Location)
    locale_info: LocaleInfo = Field(default_factory=LocaleInfo)
    goals: list[str] = Field(default_factory=list)
    income: str | None = None  # low|lower_middle|middle|upper_middle|high|very_high
    housing: str | None = (
        None  # own_home|rent|mortgage|living_with_family|temporary|homeless
    )
    tier: str | None = None  # free|basic|premium|enterprise
    accessibility: Accessibility = Field(default_factory=Accessibility)
    budget_posture: BudgetPosture = Field(default_factory=BudgetPosture)
    household: Household = Field(default_factory=Household)
    assets_high_level: list[str] = Field(default_factory=list)
```
---

## Implementation Notes

- Use this prompt as the base system prompt for all conversation nodes
- Supplement with specific node prompts for technical requirements
- Adapt tone based on user responses while maintaining core personality
- Always prioritize user comfort over information completeness
- Remember that building trust is more valuable than gathering every data point
