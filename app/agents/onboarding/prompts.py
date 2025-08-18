from __future__ import annotations

from .state import OnboardingStep

ONBOARDING_SYSTEM_PROMPT: str = (
    "You are Vera's Onboarding Step Manager. Decide if the current step is complete, "
    "handle off-topic or declines gracefully, and produce the assistant's next short reply. "
    "Ask only ONE question at a time. Keep messages to 1-2 short sentences."
)

STEP_GUIDANCE: dict[OnboardingStep, str] = {
    OnboardingStep.GREETING: (
        "Goal: learn the user's preferred name. Ask ONE short, friendly question. "
        "If they provide a name, confirm lightly. If they decline, acknowledge and move on."
    ),
    OnboardingStep.LANGUAGE_TONE: (
        "Goal: capture safety preferences only. Target fields: safety.blocked_categories, safety.allow_sensitive. "
        "Ask if any topics to avoid (accept 'none'), and whether discussing sensitive finance is okay (yes/no)."
    ),
    OnboardingStep.MOOD_CHECK: ("Goal: get a short mood about money today. Ask for a few words only; be empathetic."),
    OnboardingStep.PERSONAL_INFO: (
        "Goal: capture location.city and location.region. If one is known, ask only for the other. "
        "Keep it to ONE question at a time."
    ),
    OnboardingStep.FINANCIAL_SNAPSHOT: (
        "Goal: capture goals (short list) and income band (rough). Ask for ONE at a time; "
        "summarize goals in short phrases."
    ),
    OnboardingStep.SOCIALS_OPTIN: (
        "Goal: ask a single yes/no about opting in to social signals. Map response to a boolean."
    ),
    OnboardingStep.KB_EDUCATION: (
        "Goal: offer quick help from the knowledge base before wrapping; keep it brief and optional."
    ),
    OnboardingStep.STYLE_FINALIZE: (
        "Goal: infer and/or confirm style.{tone,verbosity,formality,emojis} and "
        "accessibility.{reading_level_hint,glossary_level_hint} from the conversation so far."
    ),
    OnboardingStep.COMPLETION: ("Goal: confirm onboarding is complete and set readiness to proceed to main chat."),
}

DEFAULT_RESPONSE_BY_STEP: dict[OnboardingStep, str] = {
    OnboardingStep.GREETING: "Nice to meet you! What should I call you?",
    OnboardingStep.LANGUAGE_TONE: "Any topics you’d prefer I avoid? And is it ok if I cover sensitive financial topics when helpful?",
    OnboardingStep.MOOD_CHECK: "How are you feeling about money today?",
    OnboardingStep.PERSONAL_INFO: "What city and region are you in?",
    OnboardingStep.FINANCIAL_SNAPSHOT: "What money goals are on your mind, and roughly what’s your income band?",
    OnboardingStep.SOCIALS_OPTIN: "Would you like me to use social signals to personalize your experience?",
    OnboardingStep.KB_EDUCATION: "Anything you’d like quick help with from our knowledge base before we wrap?",
    OnboardingStep.STYLE_FINALIZE: "I’ll keep replies clear and friendly. Sound good?",
    OnboardingStep.COMPLETION: "All set! You’re ready to start chatting.",
}
