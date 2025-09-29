from __future__ import annotations

from enum import Enum
from typing import Literal, TypedDict

from pydantic import BaseModel


class InteractionType(str, Enum):
    FREE_TEXT = "free_text"
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"


class FlowStep(str, Enum):
    PRESENTATION = "presentation"
    STEP_1_CHOICE = "step_1_choice"
    STEP_DOB_QUICK = "step_dob_quick"
    STEP_2_DOB = "step_2_dob"
    STEP_3_LOCATION = "step_3_location"
    STEP_4_HOUSING = "step_4_housing"
    STEP_4_MONEY_FEELINGS = "step_4_money_feelings"
    STEP_5_INCOME_DECISION = "step_5_income_decision"
    STEP_5_1_INCOME_EXACT = "step_5_1_income_exact"
    STEP_5_2_INCOME_RANGE = "step_5_2_income_range"
    STEP_6_CONNECT_ACCOUNTS = "step_6_connect_accounts"
    SUBSCRIPTION_NOTICE = "subscription_notice"
    COMPLETE = "complete"
    TERMINATED_UNDER_18 = "terminated_under_18"


class Choice(BaseModel):
    id: str
    label: str
    value: str
    synonyms: list[str] = []


class StepUpdateEventData(TypedDict, total=False):
    status: Literal["validating", "completed", "presented"]
    step_id: str
    step_index: int


class TokenDeltaEventData(TypedDict):
    text: str


class MessageCompletedEventData(TypedDict):
    text: str


class ChoicePayload(TypedDict):
    id: str
    label: str
    value: str
    synonyms: list[str]


class InteractionUpdateEventData(TypedDict, total=False):
    type: Literal[
        "free_text",
        "single_choice",
        "multi_choice",
    ]
    step_id: str
    step_index: int
    choices: list[ChoicePayload]


class OnboardingStatusEventData(TypedDict):
    status: Literal["done"]


class StepUpdateEvent(TypedDict):
    event: Literal["step.update"]
    data: StepUpdateEventData


class TokenDeltaEvent(TypedDict):
    event: Literal["token.delta"]
    data: TokenDeltaEventData


class MessageCompletedEvent(TypedDict):
    event: Literal["message.completed"]
    data: MessageCompletedEventData


class InteractionUpdateEvent(TypedDict):
    event: Literal["interaction.update"]
    data: InteractionUpdateEventData


class OnboardingStatusEvent(TypedDict):
    event: Literal["onboarding.status"]
    data: OnboardingStatusEventData


def parse_interaction_type(raw: str | None) -> InteractionType:
    if not raw:
        return InteractionType.FREE_TEXT
    raw_l = raw.lower().strip()
    mapping = {
        "free_text": InteractionType.FREE_TEXT,
        "single_choice": InteractionType.SINGLE_CHOICE,
        "multi_choice": InteractionType.MULTI_CHOICE,
    }
    return mapping.get(raw_l, InteractionType.FREE_TEXT)


def choice_to_payload(choice: Choice | None) -> ChoicePayload | None:
    if choice is None:
        return None
    return ChoicePayload(
        id=choice.id,
        label=choice.label,
        value=choice.value,
        synonyms=list(choice.synonyms or []),
    )


def get_step_index(step: FlowStep) -> int | None:
    mapping: dict[FlowStep, int] = {
        FlowStep.STEP_1_CHOICE: 0,
        FlowStep.STEP_2_DOB: 1,
        FlowStep.STEP_3_LOCATION: 2,
        FlowStep.STEP_4_HOUSING: 3,
        FlowStep.STEP_4_MONEY_FEELINGS: 4,
        FlowStep.STEP_5_INCOME_DECISION: 5,
        FlowStep.STEP_5_1_INCOME_EXACT: 5,
        FlowStep.STEP_5_2_INCOME_RANGE: 5,
        FlowStep.STEP_6_CONNECT_ACCOUNTS: 6,
    }
    return mapping.get(step)
