from __future__ import annotations

from contextlib import suppress
from typing import Any

from app.agents.onboarding.state import OnboardingState, OnboardingStep


class ContextPatchingService:
    def __init__(self) -> None:
        self._field_mappings = {
            OnboardingStep.GREETING: {
                "preferred_name": "identity.preferred_name",
            },
            OnboardingStep.LANGUAGE_TONE: {
                "blocked_categories": "safety.blocked_categories",
                "allow_sensitive": "safety.allow_sensitive",
            },
            OnboardingStep.PERSONAL_INFO: {
                "city": "location.city",
                "region": "location.region",
            },
            OnboardingStep.SOCIALS_OPTIN: {
                "opt_in": "social_signals_consent",
            },
            OnboardingStep.STYLE_FINALIZE: {
                "tone": "style.tone",
                "verbosity": "style.verbosity",
                "formality": "style.formality",
                "emojis": "style.emojis",
                "reading_level_hint": "accessibility.reading_level_hint",
                "glossary_level_hint": "accessibility.glossary_level_hint",
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
            elif step == OnboardingStep.STYLE_FINALIZE:
                if key in {"tone", "verbosity", "formality", "emojis"}:
                    normalized[f"style.{key}"] = value
                elif key in {"reading_level_hint", "glossary_level_hint"}:
                    normalized[f"accessibility.{key}"] = value
                else:
                    normalized[key] = value
            else:
                normalized[key] = value

        return normalized

    def apply_context_patch(self, state: OnboardingState, step: OnboardingStep, patch: dict[str, Any]) -> None:
        if not patch:
            return

        normalized_patch = self.normalize_patch_for_step(step, patch)

        for key, value in normalized_patch.items():
            if "." in key:
                self._set_by_path(state.user_context, key, value)
            else:
                try:
                    if hasattr(state.user_context, key):
                        current_attr = getattr(state.user_context, key)
                        if isinstance(current_attr, list) and not isinstance(value, list):
                            setattr(state.user_context, key, [value])
                        elif isinstance(value, dict):
                            for inner_key, inner_val in value.items():
                                self._set_by_path(state.user_context, f"{key}.{inner_key}", inner_val)
                        else:
                            setattr(state.user_context, key, value)
                    else:
                        if key == "opt_in":
                            self._set_by_path(
                                state.user_context,
                                "social_signals_consent",
                                bool(value),
                            )
                except Exception:
                    pass

        with suppress(Exception):
            state.user_context.sync_nested_to_flat()

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
                    if isinstance(current_val, list) and not isinstance(value, list):
                        value_to_set = [value]
                    else:
                        value_to_set = value
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
