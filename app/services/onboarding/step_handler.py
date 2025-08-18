from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Callable

from app.agents.onboarding.prompts import DEFAULT_RESPONSE_BY_STEP
from app.agents.onboarding.state import OnboardingState, OnboardingStep
from app.models import MemoryCategory

from .context_patching import context_patching_service
from .onboarding_reasoning import onboarding_reasoning_service


class StepHandlerService:
    def __init__(self) -> None:
        self._missing_fields_by_step: dict[OnboardingStep, list[str] | Callable] = {
            OnboardingStep.GREETING: lambda state: ["identity.preferred_name"]
            if not state.user_context.identity.preferred_name
            else [],
            OnboardingStep.LANGUAGE_TONE: self._get_language_tone_missing_fields,
            OnboardingStep.MOOD_CHECK: lambda state: ["mood"],
            OnboardingStep.PERSONAL_INFO: self._get_personal_info_missing_fields,
            OnboardingStep.FINANCIAL_SNAPSHOT: self._get_financial_snapshot_missing_fields,
            OnboardingStep.SOCIALS_OPTIN: lambda state: [],
            OnboardingStep.KB_EDUCATION: lambda state: [],
            OnboardingStep.STYLE_FINALIZE: lambda state: [],
            OnboardingStep.COMPLETION: lambda state: [],
        }

        self._completion_checks: dict[OnboardingStep, Callable[[OnboardingState], bool]] = {
            OnboardingStep.GREETING: lambda state: bool(state.user_context.identity.preferred_name),
            OnboardingStep.LANGUAGE_TONE: self._is_language_tone_complete,
            OnboardingStep.MOOD_CHECK: lambda state: any(
                getattr(m, "metadata", {}).get("type") == "mood" for m in state.semantic_memories
            ),
            OnboardingStep.PERSONAL_INFO: lambda state: bool(
                state.user_context.location.city and state.user_context.location.region
            ),
            OnboardingStep.FINANCIAL_SNAPSHOT: lambda state: bool(
                state.user_context.goals and state.user_context.income
            ),
            OnboardingStep.SOCIALS_OPTIN: lambda state: isinstance(state.user_context.social_signals_consent, bool),
            OnboardingStep.KB_EDUCATION: lambda state: True,
            OnboardingStep.STYLE_FINALIZE: lambda state: True,
            OnboardingStep.COMPLETION: lambda state: True,
        }

    async def handle_step(self, state: OnboardingState, step: OnboardingStep) -> OnboardingState:
        state.current_step = step

        missing_fields = self._get_missing_fields(state, step)

        if step == OnboardingStep.LANGUAGE_TONE and state.user_context.safety.blocked_categories is None:
            state.user_context.safety.blocked_categories = []

        decision = onboarding_reasoning_service.reason_step(state, step, missing_fields)

        context_patching_service.apply_context_patch(state, step, decision.get("patch") or {})

        if step == OnboardingStep.MOOD_CHECK:
            mood_val = (decision.get("patch") or {}).get("mood")
            if mood_val:
                state.add_semantic_memory(
                    content=f"User's current mood about money: {mood_val}",
                    category=MemoryCategory.PERSONAL,
                    metadata={"type": "mood", "value": mood_val, "context": "money"},
                )

        response = decision.get("assistant_text") or DEFAULT_RESPONSE_BY_STEP.get(step, "")

        if decision.get("complete") or self.is_step_complete(state, step):
            state.mark_step_completed(step)
            state.current_step = state.get_next_step() or self._get_default_next_step(step)

        if step == OnboardingStep.COMPLETION:
            state.user_context.ready_for_orchestrator = True
            state.ready_for_completion = True

        state.add_conversation_turn(state.last_user_message or "", response)

        return state

    async def handle_step_stream(
        self, state: OnboardingState, step: OnboardingStep
    ) -> AsyncGenerator[tuple[str, OnboardingState], None]:
        state.current_step = step

        missing_fields = self._get_missing_fields(state, step)

        if step == OnboardingStep.LANGUAGE_TONE and state.user_context.safety.blocked_categories is None:
            state.user_context.safety.blocked_categories = []

        accumulated_response = ""
        final_decision = None

        async for decision in onboarding_reasoning_service.reason_step_stream(state, step, missing_fields):
            if decision.get("streaming", False):
                chunk = decision.get("chunk", "")
                if chunk:
                    yield (chunk, state)
                    accumulated_response = decision.get("assistant_text", "")
            else:
                final_decision = decision
                break

        if final_decision:
            context_patching_service.apply_context_patch(state, step, final_decision.get("patch") or {})

            if step == OnboardingStep.MOOD_CHECK:
                mood_val = (final_decision.get("patch") or {}).get("mood")
                if mood_val:
                    state.add_semantic_memory(
                        content=f"User's current mood about money: {mood_val}",
                        category=MemoryCategory.PERSONAL,
                        metadata={"type": "mood", "value": mood_val, "context": "money"},
                    )

            if final_decision.get("complete") or self.is_step_complete(state, step):
                state.mark_step_completed(step)
                state.current_step = state.get_next_step() or self._get_default_next_step(step)

        if not accumulated_response:
            accumulated_response = (
                final_decision.get("assistant_text") if final_decision else DEFAULT_RESPONSE_BY_STEP.get(step, "")
            )

        if step == OnboardingStep.COMPLETION:
            state.user_context.ready_for_orchestrator = True
            state.ready_for_completion = True

        state.add_conversation_turn(state.last_user_message or "", accumulated_response)

        yield ("", state)

    def is_step_complete(self, state: OnboardingState, step: OnboardingStep) -> bool:
        check_func = self._completion_checks.get(step)
        if check_func:
            try:
                return check_func(state)
            except Exception:
                return False
        return False

    def _get_missing_fields(self, state: OnboardingState, step: OnboardingStep) -> list[str]:
        fields_spec = self._missing_fields_by_step.get(step)
        if callable(fields_spec):
            return fields_spec(state)
        return fields_spec or []

    def _get_language_tone_missing_fields(self, state: OnboardingState) -> list[str]:
        missing: list[str] = []
        if not state.user_context.safety.blocked_categories:
            missing.append("safety.blocked_categories")
        if state.user_context.safety.allow_sensitive is None:
            missing.append("safety.allow_sensitive")
        return missing

    def _get_personal_info_missing_fields(self, state: OnboardingState) -> list[str]:
        missing: list[str] = []
        if not state.user_context.location.city:
            missing.append("location.city")
        if not state.user_context.location.region:
            missing.append("location.region")
        return missing

    def _get_financial_snapshot_missing_fields(self, state: OnboardingState) -> list[str]:
        missing: list[str] = []
        if not state.user_context.goals:
            missing.append("goals")
        if not state.user_context.income:
            missing.append("income")
        return missing

    def _is_language_tone_complete(self, state: OnboardingState) -> bool:
        return state.user_context.safety.blocked_categories is not None and isinstance(
            state.user_context.safety.allow_sensitive, bool
        )

    def _get_default_next_step(self, current_step: OnboardingStep) -> OnboardingStep:
        step_transitions = {
            OnboardingStep.GREETING: OnboardingStep.LANGUAGE_TONE,
            OnboardingStep.LANGUAGE_TONE: OnboardingStep.MOOD_CHECK,
            OnboardingStep.MOOD_CHECK: OnboardingStep.PERSONAL_INFO,
            OnboardingStep.PERSONAL_INFO: OnboardingStep.FINANCIAL_SNAPSHOT,
            OnboardingStep.FINANCIAL_SNAPSHOT: OnboardingStep.SOCIALS_OPTIN,
            OnboardingStep.SOCIALS_OPTIN: OnboardingStep.KB_EDUCATION,
            OnboardingStep.KB_EDUCATION: OnboardingStep.STYLE_FINALIZE,
            OnboardingStep.STYLE_FINALIZE: OnboardingStep.COMPLETION,
            OnboardingStep.COMPLETION: OnboardingStep.COMPLETION,
        }
        return step_transitions.get(current_step, OnboardingStep.COMPLETION)


step_handler_service = StepHandlerService()
