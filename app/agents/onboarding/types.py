from __future__ import annotations

from enum import Enum
from typing import Any, Literal, TypedDict

from pydantic import BaseModel


class InteractionType(str, Enum):
    FREE_TEXT = "free_text"
    BINARY_CHOICE = "binary_choice"
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"
    TECHNICAL_INTEGRATION = "technical_integration"


class Choice(BaseModel):
    id: str
    label: str
    value: str
    synonyms: list[str] = []


class BinaryChoices(BaseModel):
    primary_choice: Choice | None = None
    secondary_choice: Choice | None = None


# Event payload types
class StepUpdateEventData(TypedDict):
    status: Literal["validating", "completed", "presented"]
    step_id: str


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
        "binary_choice",
        "technical_integration",
    ]
    step_id: str
    choices: list[ChoicePayload]
    primary_choice: ChoicePayload
    secondary_choice: ChoicePayload
    multi_min: int
    multi_max: int


class OnboardingStatusEventData(TypedDict):
    status: Literal["done"]


class ErrorEventData(TypedDict, total=False):
    code: str
    message: str
    step_id: str


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


class OnboardingErrorEvent(TypedDict):
    event: Literal["onboarding.error"]
    data: ErrorEventData


def parse_interaction_type(raw: str | None) -> InteractionType:
    if not raw:
        return InteractionType.FREE_TEXT
    raw_l = raw.lower().strip()
    mapping = {
        "free_text": InteractionType.FREE_TEXT,
        "binary_choice": InteractionType.BINARY_CHOICE,
        "single_choice": InteractionType.SINGLE_CHOICE,
        "multi_choice": InteractionType.MULTI_CHOICE,
        "technical_integration": InteractionType.TECHNICAL_INTEGRATION,
    }
    return mapping.get(raw_l, InteractionType.FREE_TEXT)


def choice_from_dict(data: dict[str, Any] | None) -> Choice | None:
    if not data or not isinstance(data, dict):
        return None
    try:
        return Choice(
            id=str(data.get("id", "")),
            label=str(data.get("label", "")),
            value=str(data.get("value", "")),
            synonyms=[str(s) for s in (data.get("synonyms") or [])],
        )
    except Exception:
        return None


def choices_from_list(items: list[dict[str, Any]] | None) -> list[Choice]:
    if not items:
        return []
    result: list[Choice] = []
    for it in items:
        c = choice_from_dict(it)
        if c is not None:
            result.append(c)
    return result


def choice_to_payload(choice: Choice | None) -> ChoicePayload | None:
    if choice is None:
        return None
    return ChoicePayload(
        id=choice.id,
        label=choice.label,
        value=choice.value,
        synonyms=list(choice.synonyms or []),
    )
