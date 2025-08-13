"""Onboarding agent prompts: node-specific system prompts and prompt builder."""

from __future__ import annotations

from typing import Any, Iterable

from .state import OnboardingStep
from app.models.user import UserContext

BASE_BEHAVIOR = (
    "You are Vera, a warm, supportive financial coach. Keep replies concise, kind, "
    "and clear. Ask only ONE question at a time. Avoid assumptions. Use simple words."
)

NODE_OBJECTIVES: dict[OnboardingStep, str] = {
    OnboardingStep.GREETING: (
        "Node objective: Collect identity.preferred_name. "
        "Keep the conversation in this node until it is captured and acknowledged."
    ),
    OnboardingStep.LANGUAGE_TONE: (
        "Node objective: Collect style.tone, style.verbosity, style.formality, style.emojis, "
        "and safety.blocked_categories plus safety.allow_sensitive. Stay until all are captured."
    ),
    OnboardingStep.MOOD_CHECK: (
        "Node objective: Briefly ask how the user feels about money today and capture a short mood phrase."
    ),
    OnboardingStep.PERSONAL_INFO: (
        "Node objective: Collect location.city and location.region (if unknown). Keep asking until both are captured."
    ),
    OnboardingStep.FINANCIAL_SNAPSHOT: (
        "Node objective: Collect goals (list of short strings) and income band. Keep asking until both are captured."
    ),
    OnboardingStep.SOCIALS_OPTIN: (
        "Node objective: Ask a single yes/no question for proactivity/social signals opt-in and capture as boolean."
    ),
    OnboardingStep.KB_EDUCATION: (
        "Node objective: Offer quick help (one question) about finance topics or proceed to completion if user declines."
    ),
    OnboardingStep.COMPLETION: (
        "Node objective: Politely summarize captured context and confirm that onboarding is complete."
    ),
}

SAFE_KEYS = {
    "identity": ["preferred_name", "age"],
    "style": ["tone", "verbosity", "formality", "emojis"],
    "safety": ["blocked_categories", "allow_sensitive"],
    "location": ["city", "region"],
    "locale_info": ["language", "time_zone", "currency_code"],
}


def get_node_system_prompt(step: OnboardingStep) -> str:
    base = BASE_BEHAVIOR
    obj = NODE_OBJECTIVES.get(
        step, "Node objective: Continue to collect any missing onboarding fields."
    )
    return f"{base} {obj}"


def summarize_context(ctx: UserContext) -> dict[str, Any]:
    d = ctx.model_dump()
    out: dict[str, Any] = {}
    for section, keys in SAFE_KEYS.items():
        if section in d and isinstance(d[section], dict):
            out[section] = {k: d[section].get(k) for k in keys}
    out["goals"] = d.get("goals", [])
    out["income"] = d.get("income")
    out["housing"] = d.get("housing")
    return out


def build_step_instruction(step: OnboardingStep, missing_fields: Iterable[str]) -> str:
    missing = ", ".join(missing_fields) if missing_fields else ""
    if step == OnboardingStep.GREETING:
        return f"Collect identity.preferred_name. Missing: {missing}. Ask one short question."
    if step == OnboardingStep.LANGUAGE_TONE:
        return (
            "Collect communication preferences and safety. Fields: style.tone, style.verbosity, "
            "style.formality, style.emojis, safety.blocked_categories, safety.allow_sensitive. "
            f"Missing: {missing}. Ask one short question."
        )
    if step == OnboardingStep.MOOD_CHECK:
        return "Do a short mood check about money today. Ask one empathetic question."
    if step == OnboardingStep.PERSONAL_INFO:
        return f"Collect location.city and location.region. Missing: {missing}. Ask one short question."
    if step == OnboardingStep.FINANCIAL_SNAPSHOT:
        return f"Collect goals (short strings) and income band. Missing: {missing}. Ask one short question."
    if step == OnboardingStep.SOCIALS_OPTIN:
        return "Ask a single yes/no question for opt-in."
    if step == OnboardingStep.KB_EDUCATION:
        return "Offer quick help: ask if they have a short finance question."
    if step == OnboardingStep.COMPLETION:
        return "Summarize politely what was captured and say we're ready to continue."
    return "Ask one short question to collect missing context."


def build_generation_prompt(
    *,
    step: OnboardingStep,
    user_context: UserContext,
    missing_fields: Iterable[str],
) -> tuple[str, str, dict[str, Any]]:
    system = get_node_system_prompt(step)
    instruction = build_step_instruction(step, missing_fields)
    ctx = summarize_context(user_context)
    user_prompt = (
        "Craft the next message for the user given the context.\n"
        "- Be concise and warm\n"
        "- Ask only ONE question\n"
        "- Avoid repeating previously confirmed info\n"
        "Instruction: " + instruction + "\n"
        "context: " + str(ctx)
    )
    return system, user_prompt, {"user_context": ctx, "step": step.value}
