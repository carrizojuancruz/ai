from __future__ import annotations

from .state import OnboardingStep

HOME_KEYWORDS: list[str] = [
    "house",
    "home",
    "housing",
    "rent",
    "mortgage",
    "apartment",
    "buy a house",
    "home buying",
    "real estate",
    "property",
    "living",
    "move",
    "relocate",
    "downsize",
    "upgrade home",
    "landlord",
    "lease",
    "down payment",
    "homeowner",
]

FAMILY_UNIT_KEYWORDS: list[str] = [
    "family",
    "children",
    "kids",
    "child",
    "dependents",
    "spouse",
    "partner",
    "husband",
    "wife",
    "married",
    "parent",
    "parenting",
    "childcare",
    "education fund",
    "college savings",
    "family planning",
    "baby",
    "pregnancy",
    "school",
    "daycare",
    "family expenses",
]

HEALTH_COVERAGE_KEYWORDS: list[str] = [
    "health",
    "medical",
    "doctor",
    "hospital",
    "medication",
    "insurance",
    "sick",
    "treatment",
    "therapy",
    "prescription",
    "medical bills",
    "healthcare",
    "clinic",
    "surgery",
]

KEYWORDS_BY_NODE: dict[OnboardingStep, list[str]] = {
    OnboardingStep.HOME: HOME_KEYWORDS,
    OnboardingStep.FAMILY_UNIT: FAMILY_UNIT_KEYWORDS,
    OnboardingStep.HEALTH_COVERAGE: HEALTH_COVERAGE_KEYWORDS,
}

OPTIONS_WORDS: list[str] = [
    "option",
    "options",
    "choice",
    "choices",
    "range",
    "ranges",
    "category",
    "categories",
    "example",
    "examples",
    "what are my",
    "give me",
    "show me",
    "list",
]

AGE_HESITATION_WORDS: list[str] = [
    "prefer not",
    "rather not",
    "don't want",
    "dont want",
    "not comfortable",
    "not ready",
    "not now",
    "nope",
    "nah",
]

INCOME_HESITATION_WORDS: list[str] = [
    "uncomfortable",
    "prefer not",
    "rather not",
    "don't want to share",
    "private",
]

SKIP_WORDS: list[str] = [
    "skip",
    "pass",
    "next",
    "not now",
    "maybe later",
]

UNDER_18_TOKENS: set[str] = {
    "under_18",
    "under 18",
    "<18",
    "minor",
    "teen",
    "teenager",
}
