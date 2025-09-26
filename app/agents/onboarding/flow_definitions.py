import contextlib
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from .types import Choice, FlowStep, InteractionType

if TYPE_CHECKING:
    from .state import OnboardingState

logger = logging.getLogger(__name__)


@dataclass
class StepDefinition:
    id: FlowStep
    message: str | Callable[["OnboardingState"], str]
    interaction_type: InteractionType
    choices: list[Choice] = field(default_factory=list)
    expected_field: str | None = None
    validation: Callable[[str, "OnboardingState"], tuple[bool, str | None]] | None = None
    next_step: FlowStep | Callable[[str, "OnboardingState"], FlowStep] | None = None


STEP_1_CHOICES = [
    Choice(
        id="answer_questions",
        label="Answer questions",
        value="answer_questions",
        synonyms=["questions", "yes", "sure", "okay", "let's go"],
    ),
    Choice(id="open_chat", label="Open chat", value="open_chat", synonyms=["chat", "talk", "no questions", "skip"]),
]

INCOME_DECISION_CHOICES = [
    Choice(id="income_exact", label="Sure!", value="income_exact", synonyms=["sure", "okay", "yes", "exact"]),
    Choice(
        id="income_range",
        label="I'd rather not",
        value="income_range",
        synonyms=["prefer not", "rather not", "no", "range"],
    ),
]

MONEY_FEELINGS_CHOICES = [
    Choice(id="anxious", label="Anxious", value="anxious", synonyms=["worried", "stressed", "nervous", "scared"]),
    Choice(
        id="confused",
        label="Confused",
        value="confused",
        synonyms=["lost", "unsure", "don't understand", "complicated"],
    ),
    Choice(id="zen", label="Totally zen", value="zen", synonyms=["calm", "good", "fine", "comfortable", "confident"]),
    Choice(
        id="motivated",
        label="Motivated to improve",
        value="motivated",
        synonyms=["ready", "excited", "determined", "optimistic"],
    ),
]
UNDER18_LOGOUT_CHOICES = [
    Choice(id="logout", label="Log out", value="logout", synonyms=["logout", "log out", "exit"]),
]

INCOME_RANGE_CHOICES = [
    Choice(id="under_25k", label="Under $25,000", value="under_25k", synonyms=["under 25k", "low income"]),
    Choice(id="25k_50k", label="$25,000 - $50,000", value="25k_50k", synonyms=["25-50k"]),
    Choice(id="50k_75k", label="$50,000 - $75,000", value="50k_75k", synonyms=["50-75k"]),
    Choice(id="75k_100k", label="$75,000 - $100,000", value="75k_100k", synonyms=["75-100k"]),
    Choice(id="over_100k", label="Over $100,000", value="over_100k", synonyms=["over 100k", "six figures"]),
]


def validate_name(response: str, state: "OnboardingState") -> tuple[bool, str | None]:
    if not response or len(response.strip()) < 1:
        logger.debug("[ONBOARDING] Name validation failed: empty response")
        return False, "Please tell me what you'd like to be called."
    logger.debug("[ONBOARDING] Name validation passed: %s", response.strip())
    return True, None


def validate_dob(response: str, state: "OnboardingState") -> tuple[bool, str | None]:
    try:
        import datetime as _dt

        txt = (response or "").strip()
        parsed: _dt.date | None = None
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
            try:
                parsed = _dt.datetime.strptime(txt, fmt).date()
                break
            except Exception:
                continue
        if not parsed:
            logger.debug("[ONBOARDING] DOB validation failed: unrecognized format '%s'", txt)
            return False, "Please use a valid date format like YYYY-MM-DD or MM/DD/YYYY."

        today = _dt.date.today()
        age_years = today.year - parsed.year - ((today.month, today.day) < (parsed.month, parsed.day))
        with contextlib.suppress(Exception):
            state.user_context.age = age_years
        if age_years < 18:
            logger.warning("[ONBOARDING] User is under 18 (computed age=%d)", age_years)
            return True, None

        logger.debug("[ONBOARDING] DOB validation passed; age computed=%d", age_years)
        return True, None
    except Exception as e:
        logger.error("[ONBOARDING] DOB validation error: %s", e)
        return False, "Please enter a valid date of birth."


def validate_location(response: str, state: "OnboardingState") -> tuple[bool, str | None]:
    if not response or len(response.strip()) < 3:
        logger.debug("[ONBOARDING] Location validation failed: response too short")
        return False, "Please provide your city and state."
    import re

    parts = re.split(r"[,;]", response)
    if len(parts) >= 2:
        state.user_context.location.city = parts[0].strip()
        state.user_context.location.region = parts[1].strip()
        logger.debug("[ONBOARDING] Location parsed: city=%s, region=%s", parts[0].strip(), parts[1].strip())
    else:
        state.user_context.location.city = response.strip()
        logger.debug("[ONBOARDING] Location stored as city only: %s", response.strip())
    return True, None


def validate_housing_cost(response: str, state: "OnboardingState") -> tuple[bool, str | None]:
    if not response or len(response.strip()) < 1:
        logger.debug("[ONBOARDING] Housing cost validation failed: empty response")
        return False, "Please provide your monthly rent or mortgage amount."
    state.user_context.rent_mortgage = response.strip()
    logger.debug("[ONBOARDING] Housing cost stored (rent_mortgage): %s", response.strip())
    return True, None


def get_presentation_message(state: "OnboardingState") -> str:
    return """Hi there!
I'm Vera

I'm here to make money talk easy and judgment free.
But I'm also happy to chat about life, your dreams, or the mysteries of the universe. Your choice!

By the way, what should I call you?"""


def get_step_1_message(state: "OnboardingState") -> str:
    name = state.user_context.preferred_name or "{Name}"
    return f"""Nice to meet you, {name}! So how would you like to begin?

I've got a few quick questions handy that can help personalize our chats and get to know you better. Do you have a minute to answer them?

Or we can just chat openly about what's on your mind, like an specific goal or interest you came here with.

Up to you!"""


def determine_next_step(response: str, state: "OnboardingState") -> FlowStep:
    current = state.current_flow_step
    logger.debug(
        "[ONBOARDING] Determining next step from %s with response: %s",
        current.value,
        response[:50] if response else "(empty)",
    )

    if current == FlowStep.PRESENTATION:
        name = response.strip()
        if name:
            state.user_context.preferred_name = name
            logger.info("[ONBOARDING] Name stored: %s, advancing to STEP_1_CHOICE", name)
            return FlowStep.STEP_1_CHOICE
        else:
            logger.debug("[ONBOARDING] No name provided, staying on PRESENTATION")
            return FlowStep.PRESENTATION

    elif current == FlowStep.STEP_1_CHOICE:
        response_lower = response.lower().strip()
        if any(word in response_lower for word in ["open", "chat", "skip", "no"]):
            logger.info("[ONBOARDING] User chose to skip onboarding chat, moving to STEP_DOB_QUICK")
            return FlowStep.STEP_DOB_QUICK
        logger.info("[ONBOARDING] User chose to answer questions, moving to STEP_2_DOB")
        return FlowStep.STEP_2_DOB
    elif current == FlowStep.STEP_DOB_QUICK:
        try:
            age_val = int(getattr(state.user_context, "age", 0) or 0)
        except Exception:
            age_val = 0
        if age_val < 18:
            logger.warning("[ONBOARDING] Routing to TERMINATED_UNDER_18 (age=%s) from quick DOB", age_val)
            return FlowStep.TERMINATED_UNDER_18
        logger.info("[ONBOARDING] DOB quick validated (age=%s), moving to COMPLETE", age_val)
        state.ready_for_completion = True
        return FlowStep.COMPLETE

    elif current == FlowStep.STEP_2_DOB:
        try:
            age_val = int(getattr(state.user_context, "age", 0) or 0)
        except Exception:
            age_val = 0
        if age_val < 18:
            logger.warning("[ONBOARDING] Routing to TERMINATED_UNDER_18 (age=%s)", age_val)
            return FlowStep.TERMINATED_UNDER_18
        logger.info("[ONBOARDING] DOB validated (age=%s), moving to STEP_3_LOCATION", age_val)
        return FlowStep.STEP_3_LOCATION

    elif current == FlowStep.STEP_3_LOCATION:
        logger.info("[ONBOARDING] Location stored, moving to STEP_4_HOUSING")
        return FlowStep.STEP_4_HOUSING

    elif current == FlowStep.STEP_4_HOUSING:
        logger.info("[ONBOARDING] Housing cost stored (or skipped), moving to STEP_4_MONEY_FEELINGS")
        return FlowStep.STEP_4_MONEY_FEELINGS

    elif current == FlowStep.STEP_4_MONEY_FEELINGS:
        response_lower = response.lower().strip()
        for choice in MONEY_FEELINGS_CHOICES:
            if choice.id == response or response_lower in [s.lower() for s in choice.synonyms]:
                state.user_context.money_feelings = choice.value
                logger.info("[ONBOARDING] Money feelings stored: %s", choice.value)
                break
        logger.info("[ONBOARDING] Moving to STEP_5_INCOME_DECISION")
        return FlowStep.STEP_5_INCOME_DECISION

    elif current == FlowStep.STEP_5_INCOME_DECISION:
        resp = (response or "").lower().strip()
        if "exact" in resp or resp in {"sure", "yes", "income_exact"}:
            return FlowStep.STEP_5_1_INCOME_EXACT
        return FlowStep.STEP_5_2_INCOME_RANGE

    elif current == FlowStep.STEP_5_1_INCOME_EXACT:
        state.user_context.income = response.strip() if response else None
        logger.info("[ONBOARDING] Income exact stored")
        return FlowStep.STEP_6_CONNECT_ACCOUNTS

    elif current == FlowStep.STEP_5_2_INCOME_RANGE:
        r = (response or "").lower().strip()
        for choice in INCOME_RANGE_CHOICES:
            if choice.id == response or r in [s.lower() for s in choice.synonyms] or r == choice.value:
                state.user_context.income_range = choice.value
                logger.info("[ONBOARDING] Income range stored: %s", choice.value)
                break
        return FlowStep.STEP_6_CONNECT_ACCOUNTS

    elif current == FlowStep.STEP_6_CONNECT_ACCOUNTS:
        logger.info("[ONBOARDING] Moving to COMPLETE")
        state.ready_for_completion = True
        return FlowStep.COMPLETE

    logger.warning("[ONBOARDING] Unexpected step %s, defaulting to COMPLETE", current.value)
    return FlowStep.COMPLETE


FLOW_DEFINITIONS: dict[FlowStep, StepDefinition] = {
    FlowStep.PRESENTATION: StepDefinition(
        id=FlowStep.PRESENTATION,
        message=get_presentation_message,
        interaction_type=InteractionType.FREE_TEXT,
        expected_field="preferred_name",
        validation=validate_name,
        next_step=determine_next_step,
    ),
    FlowStep.STEP_1_CHOICE: StepDefinition(
        id=FlowStep.STEP_1_CHOICE,
        message=get_step_1_message,
        interaction_type=InteractionType.SINGLE_CHOICE,
        choices=STEP_1_CHOICES,
        next_step=determine_next_step,
    ),
    FlowStep.STEP_DOB_QUICK: StepDefinition(
        id=FlowStep.STEP_DOB_QUICK,
        message="""No worries! Just a quick check: could you please tell me your date of birth?

It’s just to confirm you’re over 18, promise I’m not being nosy.""",
        interaction_type=InteractionType.FREE_TEXT,
        expected_field="dob",
        validation=validate_dob,
        next_step=determine_next_step,
    ),
    FlowStep.STEP_2_DOB: StepDefinition(
        id=FlowStep.STEP_2_DOB,
        message="""Okay then, let's get rolling!

First things first, would you mind telling me your date of birth?

It's just to confirm you're over 18, promise I'm not being nosy.""",
        interaction_type=InteractionType.FREE_TEXT,
        expected_field="dob",
        validation=validate_dob,
        next_step=determine_next_step,
    ),
    FlowStep.TERMINATED_UNDER_18: StepDefinition(
        id=FlowStep.TERMINATED_UNDER_18,
        message="""I'm really sorry, but you need to be at least 18 to chat with me. It's for safety reasons.

Please choose 'Log out' to end the session.""",
        interaction_type=InteractionType.SINGLE_CHOICE,
        choices=UNDER18_LOGOUT_CHOICES,
        next_step=lambda _r, _s: FlowStep.COMPLETE,
    ),
    FlowStep.STEP_3_LOCATION: StepDefinition(
        id=FlowStep.STEP_3_LOCATION,
        message="""And which city and state do you live in?

It helps me get a sense of local living costs because, let's be real, a smoothie bowl in LA costs more than a whole barbecue in Memphis.""",
        interaction_type=InteractionType.FREE_TEXT,
        expected_field="location",
        validation=validate_location,
        next_step=determine_next_step,
    ),
    FlowStep.STEP_4_HOUSING: StepDefinition(
        id=FlowStep.STEP_4_HOUSING,
        message="""Another piece that can be useful is what is your monthly rent or mortgage looks like.

I know, ouch. Let's pull the Band-Aid off fast. But once it's behind us, I can start piercing together your finances so I can guide you better.
If you'd rather not to, no stress, we can work around it.""",
        interaction_type=InteractionType.FREE_TEXT,
        expected_field="monthly_housing_cost",
        validation=validate_housing_cost,
        next_step=determine_next_step,
    ),
    FlowStep.STEP_4_MONEY_FEELINGS: StepDefinition(
        id=FlowStep.STEP_4_MONEY_FEELINGS,
        message="""Got it! So let's pause for a sec before we dive into more numbers.

Could you tell how do you feel about money in general? Anxious? Confused? Totally zen?

No right or wrong answers, this is a judgment-free zone. Type away or pick an option below, your call.""",
        interaction_type=InteractionType.SINGLE_CHOICE,
        choices=MONEY_FEELINGS_CHOICES,
        expected_field="money_feelings",
        next_step=determine_next_step,
    ),
    FlowStep.STEP_5_INCOME_DECISION: StepDefinition(
        id=FlowStep.STEP_5_INCOME_DECISION,
        message="""Thanks for the honesty!

Now, let's talk a few more numbers so I can get a clearer picture and help you spot money wins faster.
Something that gives me a clearer picture is your annual income. But only if you're comfortable.
You could share an exact number, pick a general range, or skip it for now.""",
        interaction_type=InteractionType.SINGLE_CHOICE,
        choices=INCOME_DECISION_CHOICES,
        next_step=determine_next_step,
    ),
    FlowStep.STEP_5_1_INCOME_EXACT: StepDefinition(
        id=FlowStep.STEP_5_1_INCOME_EXACT,
        message="""Perfect. Pop the number in below, it's just between you and me!""",
        interaction_type=InteractionType.FREE_TEXT,
        expected_field="annual_income",
        next_step=determine_next_step,
    ),
    FlowStep.STEP_5_2_INCOME_RANGE: StepDefinition(
        id=FlowStep.STEP_5_2_INCOME_RANGE,
        message="""No worries if exact numbers aren't your thing.

Would you mind sharing a rough yearly range? That would be helpful too.""",
        interaction_type=InteractionType.SINGLE_CHOICE,
        choices=INCOME_RANGE_CHOICES,
        expected_field="annual_income_range",
        next_step=determine_next_step,
    ),
    FlowStep.STEP_6_CONNECT_ACCOUNTS: StepDefinition(
        id=FlowStep.STEP_6_CONNECT_ACCOUNTS,
        message="""Got it. Now let's peek at your spending. No judgment, I'm not here to count how many lattes or tacos you buy each month.

You can safely connect your bank accounts so I can pull in the info automatically. I can only read it, I'll never touch your money.
Not ready? Totally fine. You can connect later or add expenses manually. Connected accounts just give me the clearest picture and save you extra updates each month.""",
        interaction_type=InteractionType.SINGLE_CHOICE,
        choices=[
            Choice(id="connect_now", label="Connect accounts", value="connect_now", synonyms=["connect", "link"]),
            Choice(id="not_now", label="Not right now", value="not_now", synonyms=["not now", "later", "skip"]),
        ],
        next_step=determine_next_step,
    ),
    FlowStep.COMPLETE: StepDefinition(
        id=FlowStep.COMPLETE,
        message="Thanks for sharing! I've got what I need to help you better. Let's get started!",
        interaction_type=InteractionType.FREE_TEXT,
        next_step=None,
    ),
}


def get_current_step_definition(state: "OnboardingState") -> StepDefinition:
    return FLOW_DEFINITIONS.get(state.current_flow_step, FLOW_DEFINITIONS[FlowStep.PRESENTATION])


def process_user_response(
    state: "OnboardingState", user_response: str
) -> tuple[str, FlowStep | None, InteractionType, list[Choice]]:
    current_def = get_current_step_definition(state)
    if current_def.validation:
        is_valid, error_msg = current_def.validation(user_response, state)
        if not is_valid and error_msg:
            logger.debug("[ONBOARDING] Validation failed at step %s: %s", state.current_flow_step.value, error_msg)
            return error_msg, state.current_flow_step, current_def.interaction_type, current_def.choices
    if current_def.next_step:
        if callable(current_def.next_step):
            next_step = current_def.next_step(user_response, state)
        else:
            next_step = current_def.next_step
    else:
        next_step = None
    if next_step:
        next_def = FLOW_DEFINITIONS.get(next_step)
        if next_def:
            message = next_def.message(state) if callable(next_def.message) else next_def.message
            return message, next_step, next_def.interaction_type, next_def.choices
    return "Thanks for chatting with me!", None, InteractionType.FREE_TEXT, []
