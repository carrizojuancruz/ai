from __future__ import annotations

import json
import logging
from contextlib import suppress
from typing import Any

from app.agents.onboarding.state import OnboardingState, OnboardingStep

logger = logging.getLogger(__name__)


class ContextPatchingService:
    def __init__(self) -> None:
        self._field_mappings = {
            OnboardingStep.WARMUP: {
                "preferred_name": "identity.preferred_name",
            },
            OnboardingStep.IDENTITY: {
                "preferred_name": "identity.preferred_name",
                "age": "age",
                "age_range": "age_range",
                "location": "location.city",
                "city": "location.city",
                "region": "location.region",
                "personal_goals": "goals",
            },
            OnboardingStep.INCOME_MONEY: {
                "money_feelings": "money_feelings",
                "annual_income": "income",
                "annual_income_range": "income",
                "income": "income",
                "income_range": "income",
            },
            OnboardingStep.ASSETS_EXPENSES: {
                "assets_types": "assets_high_level",
                "fixed_expenses": "expenses",
            },
            OnboardingStep.HOME: {
                "housing_type": "housing",
                "housing_satisfaction": "housing_satisfaction",
                "monthly_housing_cost": "rent_mortgage",
            },
            OnboardingStep.FAMILY_UNIT: {
                "dependents_under_18": "household.dependents_count",
                "pets": "household.pets",
            },
            OnboardingStep.HEALTH_COVERAGE: {
                "health_insurance_status": "health_insurance",
                "monthly_health_cost": "health_cost",
            },
            OnboardingStep.LEARNING_PATH: {
                "learning_interests": "learning_interests",
            },
            OnboardingStep.CHECKOUT_EXIT: {
                "final_choice": "onboarding_choice",
            },
        }

    def normalize_patch_for_step(self, step: OnboardingStep, patch: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(patch, dict):
            return {}

        normalized: dict[str, Any] = {}
        mappings = self._field_mappings.get(step, {})

        for key, value in patch.items():
            if key in mappings:
                normalized[mappings[key]] = value
            else:
                normalized[key] = value

        return normalized

    def apply_context_patch(self, state: OnboardingState, step: OnboardingStep, patch: dict[str, Any]) -> None:
        if not patch:
            return

        normalized_patch = self.normalize_patch_for_step(step, patch)

        logger.info(f"[USER CONTEXT UPDATE] Step: {step.value}")
        logger.info(f"[USER CONTEXT UPDATE] Applying patch: {json.dumps(normalized_patch, indent=2)}")

        changes = []

        for key, value in normalized_patch.items():
            if "." in key:
                self._set_by_path(state.user_context, key, value)
                changes.append(f"{key} = {value}")
            else:
                try:
                    if hasattr(state.user_context, key):
                        current_attr = getattr(state.user_context, key)
                        if isinstance(current_attr, list) and not isinstance(value, list):
                            setattr(state.user_context, key, [value])
                            changes.append(f"{key} = [{value}]")
                        elif isinstance(value, dict):
                            for inner_key, inner_val in value.items():
                                self._set_by_path(state.user_context, f"{key}.{inner_key}", inner_val)
                                changes.append(f"{key}.{inner_key} = {inner_val}")
                        else:
                            setattr(state.user_context, key, value)
                            changes.append(f"{key} = {value}")
                    else:
                        if key == "opt_in":
                            self._set_by_path(
                                state.user_context,
                                "social_signals_consent",
                                bool(value),
                            )
                            changes.append(f"social_signals_consent = {bool(value)}")
                except Exception:
                    pass

        with suppress(Exception):
            state.user_context.sync_nested_to_flat()

        if changes:
            logger.info("[USER CONTEXT UPDATE] Summary of changes:")
            for change in changes:
                logger.info(f"[USER CONTEXT UPDATE]   - {change}")

        logger.info(f"[USER CONTEXT UPDATE] Updated context: {json.dumps(state.user_context.model_dump(mode='json'), indent=2)}")

    def _set_by_path(self, obj: Any, path: str, value: Any) -> None:
        parts = [p for p in path.split(".") if p]
        if not parts:
            return

        target = obj
        for idx, part in enumerate(parts):
            is_last = idx == len(parts) - 1
            if is_last:
                try:
                    current_val = getattr(target, part, None)
                    value_to_set = [value] if isinstance(current_val, list) and not isinstance(value, list) else value
                    setattr(target, part, value_to_set)
                except Exception:
                    return
                return

            try:
                next_obj = getattr(target, part)
            except Exception:
                return

            if next_obj is None:
                return

            target = next_obj


context_patching_service = ContextPatchingService()
