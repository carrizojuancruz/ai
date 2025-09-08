from typing import Any

from app.agents.onboarding.state import OnboardingStep

WARMUP_CHOICES = [
    {
        "id": "yes",
        "label": "Let's chat!",
        "value": "yes",
        "synonyms": ["sure", "okay", "yes", "yeah", "let's go", "sounds good"],
    },
    {
        "id": "no",
        "label": "Not right now",
        "value": "no",
        "synonyms": ["no", "not now", "maybe later", "skip", "pass"],
    },
]

PLAID_CONNECT_CHOICES = [
    {
        "id": "connect_now",
        "label": "Connect now",
        "value": "connect_now",
        "synonyms": [
            "connect",
            "connect now",
            "link",
            "link accounts",
            "connect accounts",
            "yes",
        ],
    },
    {
        "id": "later",
        "label": "I prefer chatting",
        "value": "later",
        "synonyms": [
            "not now",
            "later",
            "skip",
            "do it later",
            "no",
        ],
    },
]

AGE_RANGE_CHOICES = [
    {
        "id": "under_18",
        "label": "I'm under 18",
        "value": "under_18",
        "synonyms": ["minor", "teen", "teenager", "under 18", "young"],
    },
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
        "label": "Confident and in control",
        "value": "confident",
        "synonyms": ["good", "secure", "comfortable", "in control"],
    },
    {
        "id": "learning",
        "label": "Learning and growing",
        "value": "learning",
        "synonyms": ["improving", "getting better", "figuring it out"],
    },
    {
        "id": "anxious",
        "label": "Anxious or worried",
        "value": "anxious",
        "synonyms": ["stressed", "worried", "nervous", "uncertain"],
    },
    {
        "id": "overwhelmed",
        "label": "Overwhelmed",
        "value": "overwhelmed",
        "synonyms": ["confused", "lost", "too much", "complicated"],
    },
    {
        "id": "motivated",
        "label": "Motivated to improve",
        "value": "motivated",
        "synonyms": ["ready", "excited", "determined", "optimistic"],
    },
]

LEARNING_INTERESTS_CHOICES = [
    {
        "id": "budgeting",
        "label": "Budgeting basics",
        "value": "budgeting",
        "synonyms": ["budget", "spending", "saving money"],
    },
    {
        "id": "investing",
        "label": "Investing fundamentals",
        "value": "investing",
        "synonyms": ["stocks", "investment", "portfolio", "retirement"],
    },
    {
        "id": "debt",
        "label": "Debt management",
        "value": "debt",
        "synonyms": ["loans", "credit cards", "paying off debt"],
    },
    {
        "id": "credit",
        "label": "Credit score improvement",
        "value": "credit",
        "synonyms": ["credit score", "credit report", "credit history"],
    },
    {
        "id": "goals",
        "label": "Financial goal setting",
        "value": "goals",
        "synonyms": ["planning", "goals", "future", "dreams"],
    },
    {
        "id": "emergency",
        "label": "Emergency fund building",
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
        "label": "Renting",
        "value": "rent",
        "synonyms": ["rental", "tenant", "lease", "apartment"],
    },
    {
        "id": "own",
        "label": "Own my home",
        "value": "own",
        "synonyms": ["homeowner", "mortgage", "house", "property"],
    },
    {
        "id": "family",
        "label": "Living with family",
        "value": "family",
        "synonyms": ["parents", "relatives", "family home"],
    },
    {
        "id": "other",
        "label": "Other arrangement",
        "value": "other",
        "synonyms": ["roommates", "shared", "temporary", "unique"],
    },
]

HEALTH_INSURANCE_CHOICES = [
    {
        "id": "employer",
        "label": "Through employer",
        "value": "employer",
        "synonyms": ["work", "job", "company", "employment"],
    },
    {
        "id": "self_paid",
        "label": "Self-paid",
        "value": "self_paid",
        "synonyms": ["individual", "private", "personal", "marketplace"],
    },
    {
        "id": "public",
        "label": "Public program",
        "value": "public",
        "synonyms": ["medicare", "medicaid", "government", "state"],
    },
    {
        "id": "none",
        "label": "No coverage",
        "value": "none",
        "synonyms": ["uninsured", "no insurance", "without"],
    },
]

ASSETS_TYPES_CHOICES = [
    {
        "id": "savings",
        "label": "Savings accounts",
        "value": "savings",
        "synonyms": ["savings", "emergency fund", "cash reserves"],
    },
    {
        "id": "investments",
        "label": "Investments",
        "value": "investments",
        "synonyms": ["stocks", "bonds", "mutual funds", "etf", "portfolio"],
    },
    {
        "id": "retirement",
        "label": "Retirement accounts",
        "value": "retirement",
        "synonyms": ["401k", "ira", "pension", "retirement"],
    },
    {
        "id": "real_estate",
        "label": "Real estate",
        "value": "real_estate",
        "synonyms": ["property", "house", "land", "rental property"],
    },
    {
        "id": "crypto",
        "label": "Cryptocurrency",
        "value": "crypto",
        "synonyms": ["bitcoin", "ethereum", "crypto", "digital assets"],
    },
    {
        "id": "none",
        "label": "None currently",
        "value": "none",
        "synonyms": ["no assets", "none", "nothing"],
    },
]

FIXED_EXPENSES_RANGES = [
    {
        "id": "under_1000",
        "label": "Under $1,000/month",
        "value": "under_1000",
        "synonyms": ["low expenses", "minimal", "under 1k"],
    },
    {
        "id": "1000_2000",
        "label": "$1,000 - $2,000/month",
        "value": "1000_2000",
        "synonyms": ["moderate expenses", "1-2k"],
    },
    {
        "id": "2000_3000",
        "label": "$2,000 - $3,000/month",
        "value": "2000_3000",
        "synonyms": ["average expenses", "2-3k"],
    },
    {
        "id": "3000_5000",
        "label": "$3,000 - $5,000/month",
        "value": "3000_5000",
        "synonyms": ["high expenses", "3-5k"],
    },
    {
        "id": "over_5000",
        "label": "Over $5,000/month",
        "value": "over_5000",
        "synonyms": ["very high expenses", "over 5k"],
    },
]

HOUSING_SATISFACTION_CHOICES = [
    {
        "id": "very_satisfied",
        "label": "Very satisfied",
        "value": "very_satisfied",
        "synonyms": ["love it", "perfect", "very happy"],
    },
    {
        "id": "satisfied",
        "label": "Satisfied",
        "value": "satisfied",
        "synonyms": ["good", "fine", "okay", "content"],
    },
    {
        "id": "neutral",
        "label": "Neutral",
        "value": "neutral",
        "synonyms": ["meh", "it's okay", "could be better"],
    },
    {
        "id": "unsatisfied",
        "label": "Unsatisfied",
        "value": "unsatisfied",
        "synonyms": ["not happy", "want to change", "looking to move"],
    },
    {
        "id": "very_unsatisfied",
        "label": "Very unsatisfied",
        "value": "very_unsatisfied",
        "synonyms": ["hate it", "need to move", "very unhappy"],
    },
]

DEPENDENTS_CHOICES = [
    {
        "id": "none",
        "label": "No dependents",
        "value": "none",
        "synonyms": ["no", "none", "no kids", "no children"],
    },
    {
        "id": "one",
        "label": "1 dependent",
        "value": "one",
        "synonyms": ["one", "1", "single child"],
    },
    {
        "id": "two",
        "label": "2 dependents",
        "value": "two",
        "synonyms": ["two", "2", "two children"],
    },
    {
        "id": "three_plus",
        "label": "3+ dependents",
        "value": "three_plus",
        "synonyms": ["three", "3", "multiple", "many"],
    },
]


def get_choices_for_field(field: str, step: OnboardingStep) -> dict[str, Any] | None:
    if step == OnboardingStep.WARMUP or field == "warmup_choice":
        return {
            "type": "single_choice",
            "choices": WARMUP_CHOICES,
        }

    if step == OnboardingStep.PLAID_INTEGRATION or field == "plaid_connect":
        return {
            "type": "single_choice",
            "choices": PLAID_CONNECT_CHOICES,
        }

    field_choices_map = {
        "age_range": AGE_RANGE_CHOICES,
        "income_range": INCOME_RANGE_CHOICES,
        "annual_income_range": INCOME_RANGE_CHOICES,
        "money_feelings": MONEY_FEELINGS_CHOICES,
        "learning_interests": LEARNING_INTERESTS_CHOICES,
        "housing_type": HOUSING_TYPE_CHOICES,
        "housing_satisfaction": HOUSING_SATISFACTION_CHOICES,
        "health_insurance_status": HEALTH_INSURANCE_CHOICES,
        "assets_types": ASSETS_TYPES_CHOICES,
        "fixed_expenses": FIXED_EXPENSES_RANGES,
        "dependents_under_18": DEPENDENTS_CHOICES,
    }

    if field in field_choices_map:
        if field in ["money_feelings", "learning_interests", "assets_types"]:
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
    if step == OnboardingStep.WARMUP:
        return True

    if step == OnboardingStep.CHECKOUT_EXIT and field == "final_choice":
        return True

    if step == OnboardingStep.PLAID_INTEGRATION and field == "plaid_connect":
        return True

    return field in ["learning_interests", "assets_types"]
