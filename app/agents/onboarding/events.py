from __future__ import annotations

from typing import Any

from .state import OnboardingState
from .types import (
    InteractionType,
    InteractionUpdateEvent,
    MessageCompletedEvent,
    OnboardingErrorEvent,
    OnboardingStatusEvent,
    StepUpdateEvent,
    TokenDeltaEvent,
    choice_to_payload,
)


def emit_step_update(status: str, step_id: str) -> StepUpdateEvent:
    return {
        "event": "step.update",
        "data": {"status": status, "step_id": step_id},
    }


def emit_token_delta(text: str) -> TokenDeltaEvent:
    return {"event": "token.delta", "data": {"text": text}}


def emit_message_completed(text: str) -> MessageCompletedEvent:
    return {"event": "message.completed", "data": {"text": text}}


def emit_onboarding_done() -> OnboardingStatusEvent:
    return {"event": "onboarding.status", "data": {"status": "done"}}


def emit_error(step_id: str, message: str, code: str = "internal_error") -> OnboardingErrorEvent:
    return {"event": "onboarding.error", "data": {"step_id": step_id, "message": message, "code": code}}


def build_interaction_update(state: OnboardingState) -> InteractionUpdateEvent | None:
    if state.current_interaction_type == InteractionType.FREE_TEXT:
        return None

    data: dict[str, Any] = {
        "type": state.current_interaction_type.value,
        "step_id": state.current_step.value,
    }

    if state.current_interaction_type == InteractionType.BINARY_CHOICE and state.current_binary_choices:
        pc = choice_to_payload(state.current_binary_choices.primary_choice)
        sc = choice_to_payload(state.current_binary_choices.secondary_choice)
        if pc is not None:
            data["primary_choice"] = pc
        if sc is not None:
            data["secondary_choice"] = sc
    elif state.current_interaction_type in (InteractionType.SINGLE_CHOICE, InteractionType.MULTI_CHOICE):
        data["choices"] = [
            {
                "id": c.id,
                "label": c.label,
                "value": c.value,
                "synonyms": list(c.synonyms or []),
            }
            for c in state.current_choices
        ]
        if state.current_interaction_type == InteractionType.MULTI_CHOICE:
            data["multi_min"] = state.multi_min
            data["multi_max"] = state.multi_max

    return {"event": "interaction.update", "data": data}
