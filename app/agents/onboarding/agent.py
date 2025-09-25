import json
import logging
import random
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

from app.agents.onboarding.flow_definitions import (
    determine_next_step,
    get_current_step_definition,
    process_user_response,
)
from app.agents.onboarding.state import OnboardingState
from app.agents.onboarding.types import FlowStep

from .events import (
    build_interaction_update,
    emit_message_completed,
    emit_onboarding_done,
    emit_step_update,
    emit_token_delta,
)

logger = logging.getLogger(__name__)


def _generate_text_chunks(text: str, min_chunk: int = 5, max_chunk: int = 20) -> list[str]:
    """Generate realistic text chunks for streaming simulation."""
    if not text:
        return []

    import re

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []

    for sentence in sentences:
        words = sentence.split()
        if len(words) <= max_chunk:
            chunks.append(sentence)
        else:
            current_chunk = []
            for word in words:
                current_chunk.append(word)
                if len(current_chunk) >= random.randint(min_chunk, max_chunk):
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
            if current_chunk:
                chunks.append(" ".join(current_chunk))

    result = []
    for i, chunk in enumerate(chunks):
        if i < len(chunks) - 1:
            next_chunk = chunks[i + 1]
            if chunk and chunk[-1] not in ".!?" and next_chunk and next_chunk[0].isupper():
                result.append(chunk + " ")
            else:
                result.append(chunk + (" " if not chunk.endswith((".", "!", "?")) else " "))
        else:
            result.append(chunk)

    return result


class OnboardingAgent:
    """Deterministic onboarding agent that follows a predefined flow."""

    def __init__(self, **kwargs: Any) -> None:
        logger.info("[ONBOARDING] Initialized deterministic OnboardingAgent")

    async def process_message(
        self,
        user_id: UUID,
        message: str,
        state: OnboardingState | None = None,
    ) -> tuple[str, OnboardingState]:
        if state is None:
            state = OnboardingState(user_id=user_id)
            state.current_flow_step = FlowStep.PRESENTATION

        final_response = ""
        final_state = state

        async for event, current_state in self.process_message_with_events(user_id, message, state):
            final_state = current_state
            if event and event.get("event") == "message.completed":
                final_response = event.get("data", {}).get("text", "")

        return (final_response, final_state)

    async def process_message_with_events(
        self,
        user_id: UUID,
        message: str,
        state: OnboardingState | None,
    ) -> AsyncGenerator[tuple[dict[str, Any], OnboardingState], None]:
        if state is None:
            state = OnboardingState(user_id=user_id)
            state.current_flow_step = FlowStep.PRESENTATION
            logger.info(
                "[ONBOARDING] Created new state for user_id=%s at step=%s",
                user_id,
                state.current_flow_step.value,
            )

        is_initial = (
            state.current_flow_step == FlowStep.PRESENTATION and len(state.conversation_history) == 0 and not message
        )

        if is_initial:
            logger.info(
                "[ONBOARDING] Starting initial presentation for user_id=%s",
                user_id,
            )

            step_def = get_current_step_definition(state)
            response_text = step_def.message(state) if callable(step_def.message) else step_def.message

            state.current_interaction_type = step_def.interaction_type
            state.current_choices = step_def.choices
            state.last_agent_response = response_text

            logger.info(
                "[ONBOARDING] Presenting step=%s interaction_type=%s for user_id=%s",
                state.current_flow_step.value,
                state.current_interaction_type.value,
                user_id,
            )

            yield (emit_step_update("presented", state.current_flow_step.value), state)

            for chunk in _generate_text_chunks(response_text):
                yield (emit_token_delta(chunk), state)

            yield (emit_message_completed(response_text), state)

            if step_def.interaction_type.value != "free_text":
                interaction_event = build_interaction_update(state)
                if interaction_event:
                    yield (interaction_event, state)

            yield (None, state)
            return

        state.last_user_message = message

        msg_l = (message or "").strip().lower()
        skip_tokens = {"skip", "not now", "rather not", "prefer not", "no", "not right now"}

        non_skippable = {FlowStep.PRESENTATION, FlowStep.STEP_2_DOB}

        if msg_l in skip_tokens and state.current_flow_step not in non_skippable:
            logger.info("[ONBOARDING] Skipping step=%s by user request", state.current_flow_step.value)
            old_step = state.current_flow_step
            next_step = determine_next_step("", state)
            state.current_flow_step = next_step
            next_def = get_current_step_definition(state)
            response_text = next_def.message(state) if callable(next_def.message) else next_def.message
            state.current_interaction_type = next_def.interaction_type
            state.current_choices = next_def.choices
            state.last_agent_response = response_text
            if old_step != state.current_flow_step:
                yield (emit_step_update("completed", old_step.value), state)
            for chunk in _generate_text_chunks(response_text):
                yield (emit_token_delta(chunk), state)
            yield (emit_message_completed(response_text), state)
            yield (emit_step_update("presented", state.current_flow_step.value), state)
            if state.current_interaction_type.value != "free_text":
                interaction_event = build_interaction_update(state)
                if interaction_event:
                    yield (interaction_event, state)
            if state.ready_for_completion:
                yield (emit_onboarding_done(), state)
            yield (None, state)
            return

        logger.info(
            "[ONBOARDING] Processing message for user_id=%s at step=%s: %s",
            user_id,
            state.current_flow_step.value,
            message[:100] if message else "(empty)",
        )

        yield (emit_step_update("validating", state.current_flow_step.value), state)

        response_text, next_step, interaction_type, choices = process_user_response(state, message)

        logger.info(
            "[ONBOARDING] Step transition for user_id=%s: %s -> %s",
            user_id,
            state.current_flow_step.value,
            next_step.value if next_step else "(no change)",
        )

        state.add_conversation_turn(message, response_text)

        old_step = state.current_flow_step
        if next_step:
            state.current_flow_step = next_step
            state.current_interaction_type = interaction_type
            state.current_choices = choices

            self._log_user_context(user_id, state)

        state.last_agent_response = response_text

        if next_step == FlowStep.COMPLETE or next_step == FlowStep.TERMINATED_UNDER_18:
            state.ready_for_completion = True
            state.user_context.ready_for_orchestrator = True

            logger.info(
                "[ONBOARDING] Onboarding %s for user_id=%s",
                "completed" if next_step == FlowStep.COMPLETE else "terminated (under 18)",
                user_id,
            )

            self._log_user_context(user_id, state, is_final=True)

        if old_step != state.current_flow_step:
            yield (emit_step_update("completed", old_step.value), state)

            logger.info(
                "[ONBOARDING] Completed step=%s for user_id=%s",
                old_step.value,
                user_id,
            )

        for chunk in _generate_text_chunks(response_text):
            yield (emit_token_delta(chunk), state)

        yield (emit_message_completed(response_text), state)

        yield (emit_step_update("presented", state.current_flow_step.value), state)

        if interaction_type.value != "free_text":
            state.current_interaction_type = interaction_type
            state.current_choices = choices
            interaction_event = build_interaction_update(state)
            if interaction_event:
                yield (interaction_event, state)

        if state.ready_for_completion:
            logger.info(
                "[ONBOARDING] Emitting completion event for user_id=%s",
                user_id,
            )
            yield (emit_onboarding_done(), state)

        yield (None, state)

    def _log_user_context(self, user_id: UUID, state: OnboardingState, is_final: bool = False) -> None:
        context_data = state.user_context.model_dump(exclude_none=True)

        log_data = {
            "user_id": str(user_id),
            "step": state.current_flow_step.value,
            "name": context_data.get("preferred_name"),
            "age": context_data.get("age"),
            "location": f"{context_data.get('location', {}).get('city')}, {context_data.get('location', {}).get('state')}"
            if context_data.get("location")
            else None,
            "housing_cost": context_data.get("monthly_housing_cost"),
            "living_situation": context_data.get("living_situation"),
            "money_feelings": context_data.get("money_feelings"),
        }

        log_data = {k: v for k, v in log_data.items() if v is not None}

        if is_final:
            logger.info(
                "[ONBOARDING] Final user context: %s",
                json.dumps(log_data, ensure_ascii=False),
            )
        else:
            logger.debug(
                "[ONBOARDING] User context updated: %s",
                json.dumps(log_data, ensure_ascii=False),
            )
