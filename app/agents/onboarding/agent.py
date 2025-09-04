import contextlib
import logging
from collections.abc import AsyncGenerator, Callable
from typing import Any
from uuid import UUID

from langfuse.callback import CallbackHandler
from langgraph.graph import END, StateGraph

from app.core.config import config

from .events import (
    build_interaction_update,
    emit_message_completed,
    emit_onboarding_done,
    emit_step_update,
    emit_token_delta,
)
from .prompts import validate_onboarding_prompts
from .state import OnboardingState, OnboardingStep
from .types import InteractionType

logger = logging.getLogger(__name__)


class OnboardingAgent:
    def __init__(
        self, *, step_handler_service: Any | None = None, langfuse_handler: CallbackHandler | None = None
    ) -> None:
        try:
            validate_onboarding_prompts()
        except Exception as e:
            logger.error("Onboarding prompts validation failed: %s", e)
            raise

        if step_handler_service is None:
            from app.services.onboarding.step_handler import step_handler_service as _default_handler

            step_handler_service = _default_handler
        if langfuse_handler is None:
            langfuse_handler = CallbackHandler(
                public_key=config.LANGFUSE_PUBLIC_KEY,
                secret_key=config.LANGFUSE_SECRET_KEY,
                host=config.LANGFUSE_HOST,
            )
            if not (config.LANGFUSE_PUBLIC_KEY and config.LANGFUSE_SECRET_KEY and config.LANGFUSE_HOST):
                logger.warning("Langfuse env vars missing or incomplete; callback tracing will be disabled")

        self._step_handler_service = step_handler_service
        self._langfuse_handler = langfuse_handler
        self.graph = self._create_graph()

    def _create_graph(self) -> StateGraph:
        workflow = StateGraph(OnboardingState)

        steps = [
            OnboardingStep.WARMUP,
            OnboardingStep.IDENTITY,
            OnboardingStep.INCOME_MONEY,
            OnboardingStep.ASSETS_EXPENSES,
            OnboardingStep.HOME,
            OnboardingStep.FAMILY_UNIT,
            OnboardingStep.HEALTH_COVERAGE,
            OnboardingStep.LEARNING_PATH,
            OnboardingStep.PLAID_INTEGRATION,
            OnboardingStep.CHECKOUT_EXIT,
        ]

        for step in steps:
            workflow.add_node(step.value, self._create_step_handler(step))

        workflow.add_node("route", lambda state: state)
        workflow.add_node("finished", lambda state: state)

        def _route_selector(state: OnboardingState) -> str:
            try:
                if getattr(state, "ready_for_completion", False):
                    return "finished"
            except Exception:
                pass
            return state.current_step.value

        mapping = {s.value: s.value for s in steps} | {"finished": "finished"}
        workflow.add_conditional_edges("route", _route_selector, mapping)

        for step in steps:
            workflow.add_edge(step.value, "route")
        workflow.add_edge("finished", END)

        workflow.set_entry_point("route")
        return workflow.compile()

    def _create_step_handler(self, step: OnboardingStep) -> Callable:
        async def handler(state: OnboardingState) -> OnboardingState:
            return await self._step_handler_service.handle_step(state, step)

        return handler

    async def process_message(
        self, user_id: UUID, message: str, state: OnboardingState | None = None
    ) -> tuple[str, OnboardingState]:
        if state is None:
            state = OnboardingState(user_id=user_id)
        final_state = state
        accumulated_text = ""
        async for event, current_state in self.process_message_with_events(user_id, message, state):
            final_state = current_state
            if not event:
                continue
            ev_name = event.get("event")
            if ev_name == "message.completed":
                accumulated_text = (event.get("data", {}) or {}).get("text", "") or accumulated_text
            elif ev_name == "token.delta":
                accumulated_text += (event.get("data", {}) or {}).get("text", "") or ""
        return (accumulated_text or final_state.last_agent_response or "", final_state)

    async def process_message_with_events(
        self,
        user_id: UUID,
        message: str,
        state: OnboardingState | None,
    ) -> AsyncGenerator[tuple[dict[str, Any], OnboardingState], None]:
        if state is None:
            state = OnboardingState(user_id=user_id)
        state.last_user_message = message

        prev_completed = set(s.value for s in state.completed_steps)
        current_state = state

        prev_step = state.current_step
        prev_interaction_type = state.current_interaction_type
        prev_choices = list(state.current_choices) if isinstance(state.current_choices, list) else []
        prev_binary_choices = state.current_binary_choices

        yield (emit_step_update("validating", state.current_step.value), current_state)

        step = state.current_step

        accumulated_text = ""
        async for chunk, updated_state in self._step_handler_service.handle_step_stream(state, step):
            current_state = updated_state

            if chunk:
                accumulated_text += chunk
                yield (emit_token_delta(chunk), current_state)

        yield (emit_message_completed(accumulated_text), current_state)

        with contextlib.suppress(Exception):
            current_state.ensure_completion_consistency()

        new_completed = set(s.value for s in current_state.completed_steps)
        for step_value in sorted(new_completed - prev_completed):
            yield (emit_step_update("completed", step_value), current_state)

        if current_state.current_step != prev_step:
            with contextlib.suppress(Exception):
                current_state.mark_step_transitioned(prev_step, current_state.current_step)
        with contextlib.suppress(Exception):
            current_state.mark_step_presented(current_state.current_step)

        yield (
            emit_step_update(
                "presented",
                current_state.current_step.value,
            ),
            current_state,
        )

        changed_interaction = (
            current_state.current_step != prev_step
            or current_state.current_interaction_type != prev_interaction_type
            or (
                current_state.current_interaction_type in (InteractionType.SINGLE_CHOICE, InteractionType.MULTI_CHOICE)
                and list(current_state.current_choices or []) != prev_choices
            )
            or (
                current_state.current_interaction_type == InteractionType.BINARY_CHOICE
                and (current_state.current_binary_choices != prev_binary_choices)
            )
        )

        if (
            changed_interaction
            and current_state.current_interaction_type != InteractionType.FREE_TEXT
            and current_state.current_step == step
        ):
            interaction_event = build_interaction_update(current_state)
            if interaction_event:
                yield (interaction_event, current_state)

        if current_state.ready_for_completion:
            yield (emit_onboarding_done(), current_state)
            yield (None, current_state)
            return

        yield (None, current_state)
