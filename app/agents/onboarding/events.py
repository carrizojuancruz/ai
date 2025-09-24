from __future__ import annotations

from typing import Any

from .state import OnboardingState
from .types import (
    FlowStep,
    InteractionType,
    InteractionUpdateEvent,
    MessageCompletedEvent,
    OnboardingStatusEvent,
    StepUpdateEvent,
    TokenDeltaEvent,
    get_step_index,
)


def emit_step_update(status: str, step_id: str) -> StepUpdateEvent:
    data: dict[str, Any] = {"status": status, "step_id": step_id}
    try:
        idx = get_step_index(FlowStep(step_id))
        if idx is not None:
            data["step_index"] = idx
    except Exception:
        pass
    return {"event": "step.update", "data": data}


def emit_token_delta(text: str) -> TokenDeltaEvent:
    return {"event": "token.delta", "data": {"text": text}}


def emit_message_completed(text: str) -> MessageCompletedEvent:
    return {"event": "message.completed", "data": {"text": text}}


def emit_onboarding_done() -> OnboardingStatusEvent:
    return {"event": "onboarding.status", "data": {"status": "done"}}


def build_interaction_update(state: OnboardingState) -> InteractionUpdateEvent | None:
    if state.current_interaction_type == InteractionType.FREE_TEXT:
        return None

    data: dict[str, Any] = {
        "type": state.current_interaction_type.value,
        "step_id": state.current_flow_step.value,
    }
    try:
        idx = get_step_index(FlowStep(state.current_flow_step.value))
        if idx is not None:
            data["step_index"] = idx
    except Exception:
        pass

    if state.current_interaction_type in (InteractionType.SINGLE_CHOICE, InteractionType.MULTI_CHOICE):
        data["choices"] = [
            {
                "id": c.id,
                "label": c.label,
                "value": c.value,
                "synonyms": list(c.synonyms or []),
            }
            for c in state.current_choices
        ]

    return {"event": "interaction.update", "data": data}
