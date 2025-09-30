from __future__ import annotations

import logging
from typing import Any

from app.models.user import SubscriptionTier, UserContext

logger = logging.getLogger(__name__)


def _normalize_income_range(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip().lower()
    v = v.replace("$", "").replace(",", "")
    if "+" in v or v.endswith("plus") or v.startswith(">"):
        return "over_100k" if "100k" in v else v.replace("+", "_plus").replace(" ", "_")
    v = v.replace("-", "_").replace(" ", "_")
    return v


def _merge_summary_into_context(summary: dict[str, Any], user_ctx: UserContext) -> None:
    flat_fields = [
        "preferred_name",
        "pronouns",
        "language",
        "tone_preference",
        "city",
        "dependents",
        "income_band",
        "rent_mortgage",
        "primary_financial_goal",
        "subscription_tier",
        "social_signals_consent",
        "ready_for_orchestrator",
        "age",
        "age_range",
        "housing_satisfaction",
        "health_insurance",
        "health_cost",
        "income",
        "housing",
        "tier",
    ]

    for field in flat_fields:
        value = summary.get(field)
        if value is not None:
            try:
                if field == "subscription_tier" and isinstance(value, str):
                    try:
                        value = SubscriptionTier(value)
                    except ValueError:
                        logger.warning("[CONTEXT_LOAD] Invalid subscription_tier value: %s, using default", value)
                        value = SubscriptionTier.FREE
                setattr(user_ctx, field, value)
            except Exception as e:
                logger.warning("[CONTEXT_LOAD] Could not set field %s: %s", field, e)

    list_fields = ["money_feelings", "learning_interests", "expenses", "goals", "assets_high_level"]
    for field in list_fields:
        value = summary.get(field)
        if isinstance(value, list):
            try:
                setattr(user_ctx, field, value)
            except Exception as e:
                logger.warning("[CONTEXT_LOAD] Could not set list field %s: %s", field, e)

    nested_fields = {
        "identity": ["preferred_name", "pronouns", "age"],
        "safety": ["blocked_categories", "allow_sensitive"],
        "style": ["tone", "verbosity", "formality", "emojis"],
        "location": ["city", "region", "cost_of_living", "travel", "local_rules"],
        "locale_info": ["language", "time_zone", "currency_code", "local_now_iso"],
        "accessibility": ["reading_level_hint", "glossary_level_hint"],
        "budget_posture": ["active_budget", "current_month_spend_summary"],
        "household": ["dependents_count", "household_size", "pets"],
    }

    for nested_obj_name, field_names in nested_fields.items():
        nested_data = summary.get(nested_obj_name)
        if isinstance(nested_data, dict):
            nested_obj = getattr(user_ctx, nested_obj_name)
            for field_name in field_names:
                value = nested_data.get(field_name)
                if value is not None:
                    try:
                        setattr(nested_obj, field_name, value)
                    except Exception as e:
                        logger.warning(
                            "[CONTEXT_LOAD] Could not set nested field %s.%s: %s", nested_obj_name, field_name, e
                        )


def map_ai_context_to_user_context(ai_context: dict[str, Any], user_ctx: UserContext) -> UserContext:
    summary = ai_context.get("user_context_summary")
    if isinstance(summary, dict):
        _merge_summary_into_context(summary, user_ctx)
    else:
        logger.warning("[CONTEXT_LOAD] No user_context_summary found or invalid format")

    preferred_name = ai_context.get("preferred_name")
    if isinstance(preferred_name, str) and preferred_name.strip() and not user_ctx.preferred_name:
        user_ctx.preferred_name = preferred_name.strip()

    display_prefs = ai_context.get("display_preferences") or {}
    if isinstance(display_prefs, dict):
        formality = display_prefs.get("formality")
        if isinstance(formality, str) and formality.strip() and not user_ctx.style.formality:
            user_ctx.style.formality = formality.strip()

    comm_style = ai_context.get("communication_style") or {}
    if isinstance(comm_style, dict):
        tone = comm_style.get("tone")
        if isinstance(tone, str) and tone.strip() and not user_ctx.style.tone:
            user_ctx.style.tone = tone.strip()
            user_ctx.tone_preference = tone.strip()
        detail = comm_style.get("detail_level") or comm_style.get("explanation_depth")
        if isinstance(detail, str) and detail.strip() and not user_ctx.style.verbosity:
            user_ctx.style.verbosity = detail.strip()

    collected = ai_context.get("collected_information") or {}
    if isinstance(collected, dict):
        family_size = collected.get("family_size")
        if isinstance(family_size, int) and family_size > 0 and not user_ctx.household.household_size:
            user_ctx.household.household_size = family_size

    goals_tracking = ai_context.get("goals_tracking") or {}
    if isinstance(goals_tracking, dict):
        goal_names: list[str] = [k for k, v in goals_tracking.items() if isinstance(k, str)]
        for g in goal_names:
            if g not in user_ctx.goals:
                user_ctx.goals.append(g)
        if goal_names and not user_ctx.primary_financial_goal:
            user_ctx.primary_financial_goal = goal_names[0]

    financial_ctx = ai_context.get("financial_context") or {}
    if isinstance(financial_ctx, dict):
        income_range = financial_ctx.get("income_range")
        if isinstance(income_range, str) and not user_ctx.income and not user_ctx.income_band:
            norm_income = _normalize_income_range(income_range)
            if norm_income:
                user_ctx.income = norm_income
                user_ctx.income_band = norm_income

    learning_data = ai_context.get("learning_data") or {}
    if isinstance(learning_data, dict):
        completed_topics = learning_data.get("completed_topics")
        if isinstance(completed_topics, list):
            for topic in completed_topics:
                if isinstance(topic, str) and topic and topic not in user_ctx.learning_interests:
                    user_ctx.learning_interests.append(topic)

    user_ctx.sync_flat_to_nested()
    return user_ctx


def map_user_context_to_ai_context(user_ctx: UserContext) -> dict[str, Any]:
    user_ctx.sync_flat_to_nested()

    out: dict[str, Any] = {}

    if user_ctx.preferred_name or user_ctx.identity.preferred_name:
        out["preferred_name"] = user_ctx.identity.preferred_name or user_ctx.preferred_name

    if user_ctx.style.formality:
        out.setdefault("display_preferences", {})["formality"] = user_ctx.style.formality

    if user_ctx.style.tone or user_ctx.tone_preference:
        out.setdefault("communication_style", {})["tone"] = user_ctx.style.tone or user_ctx.tone_preference
    if user_ctx.style.verbosity:
        out.setdefault("communication_style", {})["detail_level"] = user_ctx.style.verbosity

    if user_ctx.learning_interests:
        out.setdefault("learning_data", {})["completed_topics"] = list(user_ctx.learning_interests)

    if user_ctx.goals:
        goals_dict = {g: {} for g in user_ctx.goals if isinstance(g, str) and g}
        if goals_dict:
            out["goals_tracking"] = goals_dict

    if user_ctx.income or user_ctx.income_band:
        out.setdefault("financial_context", {})["income_range"] = user_ctx.income or user_ctx.income_band

    out["user_context_summary"] = user_ctx.model_dump(mode="json")

    for key in [
        "display_preferences",
        "financial_context",
        "conversation_context",
        "communication_style",
        "restrictions",
        "financial_insights",
        "behavioral_insights",
        "collected_information",
        "goals_tracking",
        "decision_patterns",
        "personalization_data",
        "learning_data",
    ]:
        out.setdefault(key, {})

    out["onboarding_completed"] = bool(getattr(user_ctx, "ready_for_orchestrator", False))
    out["is_active"] = True

    return out
