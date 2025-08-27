from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Callable

from app.agents.onboarding.prompts import DEFAULT_RESPONSE_BY_STEP
from app.agents.onboarding.state import OnboardingState, OnboardingStep

from .context_patching import context_patching_service
from .onboarding_reasoning import onboarding_reasoning_service


class StepHandlerService:
    def __init__(self) -> None:
        self._missing_fields_by_step: dict[OnboardingStep, list[str] | Callable] = {
            OnboardingStep.WARMUP: lambda state: [],
            OnboardingStep.IDENTITY: self._get_identity_missing_fields,
            OnboardingStep.INCOME_MONEY: self._get_income_money_missing_fields,
            OnboardingStep.ASSETS_EXPENSES: lambda state: ["assets_types", "fixed_expenses"],
            OnboardingStep.HOME: lambda state: ["housing_type", "housing_satisfaction"],
            OnboardingStep.FAMILY_UNIT: lambda state: ["dependents_under_18"],
            OnboardingStep.HEALTH_COVERAGE: lambda state: ["health_insurance_status"],
            OnboardingStep.LEARNING_PATH: lambda state: ["learning_interests"],
            OnboardingStep.PLAID_INTEGRATION: lambda state: [],
            OnboardingStep.CHECKOUT_EXIT: lambda state: ["final_choice"],
        }

        self._completion_checks: dict[OnboardingStep, Callable[[OnboardingState], bool]] = {
            OnboardingStep.WARMUP: lambda state: True,
            OnboardingStep.IDENTITY: self._is_identity_complete,
            OnboardingStep.INCOME_MONEY: self._is_income_money_complete,
            OnboardingStep.ASSETS_EXPENSES: lambda state: True,
            OnboardingStep.HOME: lambda state: True,
            OnboardingStep.FAMILY_UNIT: lambda state: True,
            OnboardingStep.HEALTH_COVERAGE: lambda state: True,
            OnboardingStep.LEARNING_PATH: lambda state: True,
            OnboardingStep.PLAID_INTEGRATION: lambda state: True,
            OnboardingStep.CHECKOUT_EXIT: lambda state: True,
        }

    async def handle_step(self, state: OnboardingState, step: OnboardingStep) -> OnboardingState:
        state.current_step = step

        if step in [OnboardingStep.HOME, OnboardingStep.FAMILY_UNIT, OnboardingStep.HEALTH_COVERAGE] and not state.should_show_conditional_node(step):
            state.current_step = state.get_next_step() or OnboardingStep.PLAID_INTEGRATION
            return state

        missing_fields = self._get_missing_fields(state, step)

        if step == OnboardingStep.IDENTITY:
            age = state.user_context.age
            age_range = state.user_context.age_range
            if (age and int(age) < 18) or age_range == "under_18":
                state.ready_for_completion = True
                response = "I appreciate your interest, but I'm designed to help adults (18+) with their finances. Please come back when you're 18 or older!"
                state.add_conversation_turn(state.last_user_message or "", response)
                return state

        decision = onboarding_reasoning_service.reason_step(state, step, missing_fields)

        context_patching_service.apply_context_patch(state, step, decision.get("patch") or {})

        response = decision.get("assistant_text") or DEFAULT_RESPONSE_BY_STEP.get(step, "")

        state.current_interaction_type = decision.get("interaction_type", "free_text")
        state.current_choices = decision.get("choices", [])
        if decision.get("interaction_type") == "binary_choice":
            state.current_binary_choices = {
                "primary_choice": decision.get("primary_choice"),
                "secondary_choice": decision.get("secondary_choice"),
            }
        else:
            state.current_binary_choices = None
        state.multi_min = decision.get("multi_min")
        state.multi_max = decision.get("multi_max")

        if decision.get("complete") or self.is_step_complete(state, step):
            state.mark_step_completed(step)
            state.current_step = state.get_next_step() or OnboardingStep.CHECKOUT_EXIT

        if decision.get("declined") or (
            state.last_user_message
            and any(
                skip_word in state.last_user_message.lower()
                for skip_word in ["skip", "pass", "next", "not now", "maybe later"]
            )
        ):
            state = self._handle_skip(state, step)

        if step == OnboardingStep.WARMUP:
            if state.last_user_message and any(
                skip_word in state.last_user_message.lower()
                for skip_word in ["skip to account", "just setup", "skip onboarding"]
            ):
                state.current_step = OnboardingStep.CHECKOUT_EXIT
                response = "No problem! Let's get your account set up."

        elif step == OnboardingStep.CHECKOUT_EXIT:
            state.user_context.ready_for_orchestrator = True
            state.ready_for_completion = True

        state.add_conversation_turn(state.last_user_message or "", response)

        return state

    async def handle_step_stream(
        self, state: OnboardingState, step: OnboardingStep
    ) -> AsyncGenerator[tuple[str, OnboardingState], None]:
        state.current_step = step

        if step in [OnboardingStep.HOME, OnboardingStep.FAMILY_UNIT, OnboardingStep.HEALTH_COVERAGE] and not state.should_show_conditional_node(step):
            state.current_step = state.get_next_step() or OnboardingStep.PLAID_INTEGRATION
            yield ("", state)
            return

        missing_fields = self._get_missing_fields(state, step)

        if step == OnboardingStep.IDENTITY:
            age = state.user_context.age
            age_range = state.user_context.age_range
            if (age and int(age) < 18) or age_range == "under_18":
                state.ready_for_completion = True
                response = "I appreciate your interest, but I'm designed to help adults (18+) with their finances. Please come back when you're 18 or older!"
                state.add_conversation_turn(state.last_user_message or "", response)
                yield (response, state)
                return

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

            state.current_interaction_type = final_decision.get("interaction_type", "free_text")
            state.current_choices = final_decision.get("choices", [])
            if final_decision.get("interaction_type") == "binary_choice":
                state.current_binary_choices = {
                    "primary_choice": final_decision.get("primary_choice"),
                    "secondary_choice": final_decision.get("secondary_choice"),
                }
            else:
                state.current_binary_choices = None
            state.multi_min = final_decision.get("multi_min")
            state.multi_max = final_decision.get("multi_max")

            if final_decision.get("complete") or self.is_step_complete(state, step):
                state.mark_step_completed(step)
                state.current_step = state.get_next_step() or OnboardingStep.CHECKOUT_EXIT

            if final_decision.get("declined") or (
                state.last_user_message
                and any(
                    skip_word in state.last_user_message.lower()
                    for skip_word in ["skip", "pass", "next", "not now", "maybe later"]
                )
            ):
                state = self._handle_skip(state, step)

            if step == OnboardingStep.WARMUP:
                if state.last_user_message and any(
                    skip_word in state.last_user_message.lower()
                    for skip_word in ["skip to account", "just setup", "skip onboarding"]
                ):
                    state.current_step = OnboardingStep.CHECKOUT_EXIT
                    accumulated_response = "No problem! Let's get your account set up."

            elif step == OnboardingStep.CHECKOUT_EXIT:
                state.user_context.ready_for_orchestrator = True
                state.ready_for_completion = True

            if not accumulated_response:
                accumulated_response = (
                    final_decision.get("assistant_text") if final_decision else ""
                ) or DEFAULT_RESPONSE_BY_STEP.get(step, "")

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

    def _get_identity_missing_fields(self, state: OnboardingState) -> list[str]:
        missing: list[str] = []
        has_age = bool(getattr(state.user_context, "age", None))
        has_age_range = bool(getattr(state.user_context, "age_range", None))
        if not has_age and not has_age_range:
            missing.append("age_range")
        if not getattr(state.user_context.location, "city", None):
            missing.append("location")
        if not getattr(state.user_context, "goals", None):
            missing.append("personal_goals")
        return missing

    def _get_income_money_missing_fields(self, state: OnboardingState) -> list[str]:
        missing: list[str] = []
        if not getattr(state.user_context, "money_feelings", None):
            missing.append("money_feelings")
        has_income = bool(getattr(state.user_context, "income", None))
        has_income_range = bool(getattr(state.user_context, "income_range", None))
        has_annual_income_range = bool(getattr(state.user_context, "annual_income_range", None))
        if not (has_income or has_income_range or has_annual_income_range):
            missing.append("annual_income_range")
        return missing

    def _is_identity_complete(self, state: OnboardingState) -> bool:
        return bool((state.user_context.age or state.user_context.age_range) and state.user_context.location.city)

    def _is_income_money_complete(self, state: OnboardingState) -> bool:
        return hasattr(state.user_context, "money_feelings") or state.user_context.income is not None

    def _get_default_next_step(self, current_step: OnboardingStep) -> OnboardingStep:
        return OnboardingStep.CHECKOUT_EXIT

    def _handle_skip(self, state: OnboardingState, step: OnboardingStep) -> OnboardingState:
        if step not in [OnboardingStep.WARMUP, OnboardingStep.IDENTITY, OnboardingStep.PLAID_INTEGRATION]:
            state.skip_count += 1
            state.skipped_nodes.append(step.value)
            state.mark_step_skipped(step)
            if state.skip_count >= 3:
                state.current_step = OnboardingStep.PLAID_INTEGRATION

        return state


step_handler_service = StepHandlerService()
