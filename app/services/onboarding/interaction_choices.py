from typing import Any

from app.agents.onboarding.state import OnboardingStep

AGE_RANGE_CHOICES = [
    {
        "id": "18_24",
        "label": "18-24 years",
        "value": "18_24",
        "synonyms": ["young adult", "college age", "early twenties"],
    },
    {
        "id": "25_34",
        "label": "25-34 years",
        "value": "25_34",
        "synonyms": ["mid twenties", "early thirties", "young professional"],
    },
    {
        "id": "35_44",
        "label": "35-44 years",
        "value": "35_44",
        "synonyms": ["mid thirties", "early forties", "established"],
    },
    {
        "id": "45_54",
        "label": "45-54 years",
        "value": "45_54",
        "synonyms": ["mid forties", "early fifties", "middle age"],
    },
    {
        "id": "55_64",
        "label": "55-64 years",
        "value": "55_64",
        "synonyms": ["mid fifties", "early sixties", "pre-retirement"],
    },
    {
        "id": "over_65",
        "label": "65+ years",
        "value": "over_65",
        "synonyms": ["senior", "retired", "retirement age"],
    },
]

INCOME_RANGE_CHOICES = [
    {
        "id": "under_25k",
        "label": "Under $25,000",
        "value": "under_25k",
        "synonyms": ["low income", "under 25k", "less than 25000"],
    },
    {
        "id": "25k_50k",
        "label": "$25,000 - $50,000",
        "value": "25k_50k",
        "synonyms": ["25-50k", "moderate income"],
    },
    {
        "id": "50k_75k",
        "label": "$50,000 - $75,000",
        "value": "50k_75k",
        "synonyms": ["50-75k", "middle income"],
    },
    {
        "id": "75k_100k",
        "label": "$75,000 - $100,000",
        "value": "75k_100k",
        "synonyms": ["75-100k", "upper middle income"],
    },
    {
        "id": "over_100k",
        "label": "Over $100,000",
        "value": "over_100k",
        "synonyms": ["high income", "six figures", "over 100k"],
    },
]

MONEY_FEELINGS_CHOICES = [
    {
        "id": "confident",
        "label": "💪 Confident and in control",
        "value": "confident",
        "synonyms": ["good", "secure", "comfortable", "in control"],
    },
    {
        "id": "learning",
        "label": "📚 Learning and growing",
        "value": "learning",
        "synonyms": ["improving", "getting better", "figuring it out"],
    },
    {
        "id": "anxious",
        "label": "😰 Anxious or worried",
        "value": "anxious",
        "synonyms": ["stressed", "worried", "nervous", "uncertain"],
    },
    {
        "id": "overwhelmed",
        "label": "😵 Overwhelmed",
        "value": "overwhelmed",
        "synonyms": ["confused", "lost", "too much", "complicated"],
    },
    {
        "id": "motivated",
        "label": "🎯 Motivated to improve",
        "value": "motivated",
        "synonyms": ["ready", "excited", "determined", "optimistic"],
    },
]

LEARNING_INTERESTS_CHOICES = [
    {
        "id": "budgeting",
        "label": "💰 Budgeting basics",
        "value": "budgeting",
        "synonyms": ["budget", "spending", "saving money"],
    },
    {
        "id": "investing",
        "label": "📈 Investing fundamentals",
        "value": "investing",
        "synonyms": ["stocks", "investment", "portfolio", "retirement"],
    },
    {
        "id": "debt",
        "label": "💳 Debt management",
        "value": "debt",
        "synonyms": ["loans", "credit cards", "paying off debt"],
    },
    {
        "id": "credit",
        "label": "📊 Credit score improvement",
        "value": "credit",
        "synonyms": ["credit score", "credit report", "credit history"],
    },
    {
        "id": "goals",
        "label": "🎯 Financial goal setting",
        "value": "goals",
        "synonyms": ["planning", "goals", "future", "dreams"],
    },
    {
        "id": "emergency",
        "label": "🛡️ Emergency fund building",
        "value": "emergency",
        "synonyms": ["emergency fund", "rainy day", "savings"],
    },
]

CHECKOUT_CHOICES = {
    "primary_choice": {
        "id": "keep_chatting",
        "label": "Keep chatting",
        "value": "keep_chatting",
        "synonyms": ["chat", "talk more", "continue conversation", "yes"],
    },
    "secondary_choice": {
        "id": "lets_go",
        "label": "Let's go!",
        "value": "lets_go",
        "synonyms": ["start", "begin", "ready", "setup", "no"],
    },
}

HOUSING_TYPE_CHOICES = [
    {
        "id": "rent",
        "label": "🏠 Renting",
        "value": "rent",
        "synonyms": ["rental", "tenant", "lease", "apartment"],
    },
    {
        "id": "own",
        "label": "🏡 Own my home",
        "value": "own",
        "synonyms": ["homeowner", "mortgage", "house", "property"],
    },
    {
        "id": "family",
        "label": "👨‍👩‍👧 Living with family",
        "value": "family",
        "synonyms": ["parents", "relatives", "family home"],
    },
    {
        "id": "other",
        "label": "🏘️ Other arrangement",
        "value": "other",
        "synonyms": ["roommates", "shared", "temporary", "unique"],
    },
]

HEALTH_INSURANCE_CHOICES = [
    {
        "id": "employer",
        "label": "🏢 Through employer",
        "value": "employer",
        "synonyms": ["work", "job", "company", "employment"],
    },
    {
        "id": "self_paid",
        "label": "💰 Self-paid",
        "value": "self_paid",
        "synonyms": ["individual", "private", "personal", "marketplace"],
    },
    {
        "id": "public",
        "label": "🏛️ Public program",
        "value": "public",
        "synonyms": ["medicare", "medicaid", "government", "state"],
    },
    {
        "id": "none",
        "label": "❌ No coverage",
        "value": "none",
        "synonyms": ["uninsured", "no insurance", "without"],
    },
]


def get_choices_for_field(field: str, step: OnboardingStep) -> dict[str, Any] | None:
    field_choices_map = {
        "age_range": AGE_RANGE_CHOICES,
        "income_range": INCOME_RANGE_CHOICES,
        "annual_income_range": INCOME_RANGE_CHOICES,
        "money_feelings": MONEY_FEELINGS_CHOICES,
        "learning_interests": LEARNING_INTERESTS_CHOICES,
        "housing_type": HOUSING_TYPE_CHOICES,
        "health_insurance_status": HEALTH_INSURANCE_CHOICES,
    }

    if field in field_choices_map:
        if field in ["money_feelings", "learning_interests"]:
            return {
                "type": "multi_choice",
                "choices": field_choices_map[field],
                "multi_min": 1,
                "multi_max": 3,
            }
        else:
            return {
                "type": "single_choice",
                "choices": field_choices_map[field],
            }

    if step == OnboardingStep.CHECKOUT_EXIT and field == "final_choice":
        return {
            "type": "binary_choice",
            "primary_choice": CHECKOUT_CHOICES["primary_choice"],
            "secondary_choice": CHECKOUT_CHOICES["secondary_choice"],
        }

    return None


def should_always_offer_choices(step: OnboardingStep, field: str) -> bool:
    if step == OnboardingStep.CHECKOUT_EXIT and field == "final_choice":
        return True

    if step == OnboardingStep.LEARNING_PATH and field == "learning_interests":
        return True

    return bool(step == OnboardingStep.INCOME_MONEY and field == "money_feelings")
