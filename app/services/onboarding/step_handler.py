from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Callable

from app.agents.onboarding.constants import SKIP_WORDS, UNDER_18_TOKENS
from app.agents.onboarding.formatter import format_brief
from app.agents.onboarding.prompts import DEFAULT_RESPONSE_BY_STEP
from app.agents.onboarding.prompts import UNDER_18_TERMINATION_MESSAGE as UNDER_18_MESSAGE
from app.agents.onboarding.state import OnboardingState, OnboardingStep
from app.agents.onboarding.types import (
    BinaryChoices,
    InteractionType,
    choice_from_dict,
    choices_from_list,
)
from app.services.onboarding.interaction_choices import get_choices_for_field

from .context_patching import context_patching_service
from .onboarding_reasoning import onboarding_reasoning_service

PLAID_VALID_RESPONSES = {"connect_now", "later"}


class StepHandlerService:
    def __init__(self) -> None:
        self._missing_fields_by_step: dict[OnboardingStep, list[str] | Callable] = {
            OnboardingStep.WARMUP: lambda state: ["warmup_choice"],
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
            OnboardingStep.WARMUP: self._is_warmup_complete,
            OnboardingStep.IDENTITY: self._is_identity_complete,
            OnboardingStep.INCOME_MONEY: self._is_income_money_complete,
            OnboardingStep.ASSETS_EXPENSES: self._is_assets_expenses_complete,
            OnboardingStep.HOME: self._is_home_complete,
            OnboardingStep.FAMILY_UNIT: self._is_family_unit_complete,
            OnboardingStep.HEALTH_COVERAGE: self._is_health_coverage_complete,
            OnboardingStep.LEARNING_PATH: self._is_learning_path_complete,
            OnboardingStep.PLAID_INTEGRATION: self._is_plaid_integration_complete,
            OnboardingStep.CHECKOUT_EXIT: self._is_checkout_exit_complete,
        }

    def _message_indicates_under_18(self, state: OnboardingState) -> bool:
        msg = (state.last_user_message or "").strip().lower()
        return msg in UNDER_18_TOKENS

    def _context_indicates_under_18(self, state: OnboardingState) -> bool:
        try:
            age = getattr(state.user_context, "age", None)
            age_range = getattr(state.user_context, "age_range", None)
            return bool((age and int(age) < 18) or age_range == "under_18")
        except Exception:
            return False

    def _terminate_for_under_18(self, state: OnboardingState) -> None:
        state.ready_for_completion = True
        state.user_context.ready_for_orchestrator = True
        state.add_conversation_turn(state.last_user_message or "", format_brief(UNDER_18_MESSAGE))

    def _mark_ready_if_checkout_exit(self, state: OnboardingState) -> None:
        if state.current_step == OnboardingStep.CHECKOUT_EXIT:
            state.user_context.ready_for_orchestrator = True
            state.ready_for_completion = True

    def _ensure_single_choice_for_field(self, state: OnboardingState, target_step: OnboardingStep, field: str) -> None:
        if state.current_step == target_step and state.current_interaction_type == InteractionType.FREE_TEXT:
            choice_info = get_choices_for_field(field, target_step)
            if choice_info and choice_info.get("choices"):
                state.current_interaction_type = InteractionType(choice_info["type"])
                state.current_choices = choices_from_list(choice_info.get("choices"))

    def _ensure_warmup_choices(self, state: OnboardingState) -> None:
        self._ensure_single_choice_for_field(state, OnboardingStep.WARMUP, "warmup_choice")

    def _ensure_plaid_choices(self, state: OnboardingState) -> None:
        self._ensure_single_choice_for_field(state, OnboardingStep.PLAID_INTEGRATION, "plaid_connect")

    async def handle_step(self, state: OnboardingState, step: OnboardingStep) -> OnboardingState:
        state.current_step = step

        state.current_interaction_type = InteractionType.FREE_TEXT
        state.current_choices = []
        state.current_binary_choices = None
        state.multi_min = None
        state.multi_max = None

        missing_fields = self._get_missing_fields(state, step)

        if step == OnboardingStep.IDENTITY and self._message_indicates_under_18(state):
            self._terminate_for_under_18(state)
            return state

        if step == OnboardingStep.IDENTITY and self._context_indicates_under_18(state):
            self._terminate_for_under_18(state)
            return state

        if step == OnboardingStep.PLAID_INTEGRATION:
            self._ensure_plaid_choices(state)
            response = "Ready to connect your accounts securely?"
            state.add_conversation_turn(state.last_user_message or "", format_brief(response))
            if (state.last_user_message or "").strip().lower() in PLAID_VALID_RESPONSES:
                state.mark_step_completed(step)
                state.user_context.ready_for_orchestrator = True
                state.ready_for_completion = True
            return state

        decision = onboarding_reasoning_service.reason_step(state, step, missing_fields)

        context_patching_service.apply_context_patch(state, step, decision.get("patch") or {})

        if step == OnboardingStep.IDENTITY and self._context_indicates_under_18(state):
            self._terminate_for_under_18(state)
            return state

        response = decision.get("assistant_text") or DEFAULT_RESPONSE_BY_STEP.get(step, "")

        if (
            decision.get("interaction_type") in ["single_choice", "multi_choice", "binary_choice"]
            and response
            and any(prefix in response for prefix in ["- ", "• ", "* ", "1.", "2.", "3."])
        ):
            lines = [ln for ln in response.splitlines() if not ln.strip().startswith(("-", "•", "*", "1.", "2.", "3."))]
            response = "\n".join(lines).strip()

        itype = InteractionType(decision.get("interaction_type", "free_text"))
        state.current_interaction_type = itype
        state.current_choices = choices_from_list(decision.get("choices"))
        if itype == InteractionType.BINARY_CHOICE:
            state.current_binary_choices = BinaryChoices(
                primary_choice=choice_from_dict(decision.get("primary_choice")),
                secondary_choice=choice_from_dict(decision.get("secondary_choice")),
            )
        else:
            state.current_binary_choices = None
        state.multi_min = decision.get("multi_min")
        state.multi_max = decision.get("multi_max")

        if itype == InteractionType.BINARY_CHOICE and not (
            state.current_binary_choices
            and (state.current_binary_choices.primary_choice or state.current_binary_choices.secondary_choice)
        ):
            state.current_interaction_type = InteractionType.FREE_TEXT
            state.current_binary_choices = None

        self._ensure_warmup_choices(state)

        if decision.get("complete") or self.is_step_complete(state, step):
            state.mark_step_completed(step)
            state.current_step = state.get_next_step() or OnboardingStep.CHECKOUT_EXIT
            self._mark_ready_if_checkout_exit(state)

        if decision.get("declined") or (
            state.last_user_message and any(skip_word in state.last_user_message.lower() for skip_word in SKIP_WORDS)
        ):
            state = self._handle_skip(state, step)
            self._mark_ready_if_checkout_exit(state)

        if step == OnboardingStep.WARMUP:
            if state.last_user_message and any(
                skip_word in state.last_user_message.lower()
                for skip_word in ["skip to account", "just setup", "skip onboarding"]
            ):
                state.current_step = OnboardingStep.CHECKOUT_EXIT
                response = "No problem! Let's get your account set up."
                self._mark_ready_if_checkout_exit(state)

        elif step == OnboardingStep.CHECKOUT_EXIT:
            state.user_context.ready_for_orchestrator = True
            state.ready_for_completion = True

        state.add_conversation_turn(state.last_user_message or "", format_brief(response))

        return state

    async def handle_step_stream(
        self, state: OnboardingState, step: OnboardingStep
    ) -> AsyncGenerator[tuple[str, OnboardingState], None]:
        try:
            state.current_step = step

            state.current_interaction_type = InteractionType.FREE_TEXT
            state.current_choices = []
            state.current_binary_choices = None
            state.multi_min = None
            state.multi_max = None

            if step == OnboardingStep.IDENTITY and self._message_indicates_under_18(state):
                self._terminate_for_under_18(state)
                yield (UNDER_18_MESSAGE, state)
                return

            if step == OnboardingStep.IDENTITY and self._context_indicates_under_18(state):
                self._terminate_for_under_18(state)
                yield (UNDER_18_MESSAGE, state)
                return

            if step == OnboardingStep.PLAID_INTEGRATION:
                self._ensure_plaid_choices(state)
                response = "Ready to connect your accounts securely?"
                state.add_conversation_turn(state.last_user_message or "", format_brief(response))
                yield (format_brief(response), state)
                if (state.last_user_message or "").strip().lower() in PLAID_VALID_RESPONSES:
                    state.mark_step_completed(step)
                    state.user_context.ready_for_orchestrator = True
                    state.ready_for_completion = True
                return

            missing_fields = self._get_missing_fields(state, step)

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

                if step == OnboardingStep.IDENTITY and self._context_indicates_under_18(state):
                    self._terminate_for_under_18(state)
                    yield (UNDER_18_MESSAGE, state)
                    return

                state.current_interaction_type = InteractionType(final_decision.get("interaction_type", "free_text"))
                state.current_choices = choices_from_list(final_decision.get("choices"))
                if state.current_interaction_type == InteractionType.BINARY_CHOICE:
                    state.current_binary_choices = BinaryChoices(
                        primary_choice=choice_from_dict(final_decision.get("primary_choice")),
                        secondary_choice=choice_from_dict(final_decision.get("secondary_choice")),
                    )
                else:
                    state.current_binary_choices = None
                state.multi_min = final_decision.get("multi_min")
                state.multi_max = final_decision.get("multi_max")

                if state.current_interaction_type == InteractionType.BINARY_CHOICE and not (
                    state.current_binary_choices
                    and (state.current_binary_choices.primary_choice or state.current_binary_choices.secondary_choice)
                ):
                    state.current_interaction_type = InteractionType.FREE_TEXT
                    state.current_binary_choices = None

                self._ensure_warmup_choices(state)

                if final_decision.get("complete") or self.is_step_complete(state, step):
                    state.mark_step_completed(step)
                    state.current_step = state.get_next_step() or OnboardingStep.CHECKOUT_EXIT
                    self._mark_ready_if_checkout_exit(state)

                if final_decision.get("declined") or (
                    state.last_user_message
                    and any(skip_word in state.last_user_message.lower() for skip_word in SKIP_WORDS)
                ):
                    state = self._handle_skip(state, step)
                    self._mark_ready_if_checkout_exit(state)

                if final_decision.get("interaction_type") in ["single_choice", "multi_choice", "binary_choice"] and any(
                    tok in (accumulated_response or "") for tok in ["18-", "66+", "-24", "-34", "-44", "-54", "-64"]
                ):
                    accumulated_response = ""

                if step == OnboardingStep.WARMUP:
                    if state.last_user_message and any(
                        skip_word in state.last_user_message.lower()
                        for skip_word in ["skip to account", "just setup", "skip onboarding"]
                    ):
                        state.current_step = OnboardingStep.CHECKOUT_EXIT
                        accumulated_response = "No problem! Let's get your account set up."
                        self._mark_ready_if_checkout_exit(state)

                elif step == OnboardingStep.CHECKOUT_EXIT:
                    state.user_context.ready_for_orchestrator = True
                    state.ready_for_completion = True

                if final_decision and final_decision.get("interaction_type") in [
                    "single_choice",
                    "multi_choice",
                    "binary_choice",
                ]:
                    accumulated_response = final_decision.get("assistant_text") or ""

                if not accumulated_response:
                    accumulated_response = (
                        final_decision.get("assistant_text") if final_decision else ""
                    ) or DEFAULT_RESPONSE_BY_STEP.get(step, "")

                if (
                    final_decision
                    and final_decision.get("interaction_type") in ["single_choice", "multi_choice", "binary_choice"]
                    and accumulated_response
                    and any(prefix in accumulated_response for prefix in ["- ", "• ", "* ", "1.", "2.", "3."])
                ):
                    lines = [
                        ln
                        for ln in accumulated_response.splitlines()
                        if not ln.strip().startswith(("-", "•", "*", "1.", "2.", "3."))
                    ]
                    accumulated_response = "\n".join(lines).strip()

                state.add_conversation_turn(state.last_user_message or "", format_brief(accumulated_response))

            yield ("", state)
        except Exception:
            safe_text = format_brief("Sorry, I had trouble processing that. Let's continue and try again.")
            state.add_conversation_turn(state.last_user_message or "", safe_text)
            yield (safe_text, state)

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
        if not getattr(state.user_context, "preferred_name", None):
            missing.append("preferred_name")
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

    def _is_warmup_complete(self, state: OnboardingState) -> bool:
        return bool(state.last_user_message and state.last_user_message.strip() and len(state.conversation_history) > 0)

    def _is_assets_expenses_complete(self, state: OnboardingState) -> bool:
        return True

    def _is_home_complete(self, state: OnboardingState) -> bool:
        return len(self._get_missing_fields(state, OnboardingStep.HOME)) == 0

    def _is_family_unit_complete(self, state: OnboardingState) -> bool:
        return len(self._get_missing_fields(state, OnboardingStep.FAMILY_UNIT)) == 0

    def _is_health_coverage_complete(self, state: OnboardingState) -> bool:
        return len(self._get_missing_fields(state, OnboardingStep.HEALTH_COVERAGE)) == 0

    def _is_learning_path_complete(self, state: OnboardingState) -> bool:
        return True

    def _is_plaid_integration_complete(self, state: OnboardingState) -> bool:
        return True

    def _is_checkout_exit_complete(self, state: OnboardingState) -> bool:
        return True

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
