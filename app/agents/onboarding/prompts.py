"""Onboarding agent prompts: node-specific system prompts and prompt builder."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.models.user import UserContext

from .state import OnboardingStep

BASE_BEHAVIOR = (
    "You are Vera, a warm, supportive financial coach. Keep replies concise, kind, "
    "and clear. Ask only ONE question at a time. Avoid assumptions. Use simple words."
)

GUARDRAILS = (
    "- Never ask more than one question at a time.\n"
    "- Acknowledge small talk briefly, then pivot back to the single required question.\n"
    "- Do not repeat the exact same wording twice in a row; rephrase if you must retry.\n"
    "- If the user explicitly declines a field, acknowledge gracefully and try ONE lighter alternative;"
    " if they decline again, stop retrying for this node.\n"
    "- Keep messages to one or two short sentences."
)

UNIT_RULES: dict[OnboardingStep, str] = {
    OnboardingStep.GREETING: (
        "- If no name is provided, ask for the preferred name with a fresh phrasing.\n"
        "- If the user declines to share a name now, acknowledge kindly and offer a nickname option once."
    ),
    OnboardingStep.LANGUAGE_TONE: (
        "- Ask ONLY about safety: blocked topics and whether sensitive content is okay.\n"
        "- If the user says 'none' or 'no' for blocked topics, accept an empty list and move on.\n"
        "- If the answer to sensitive content is unclear, ask a simple yes/no once."
    ),
    OnboardingStep.MOOD_CHECK: (
        "- Ask for a short phrase about how they feel regarding money today.\n"
        "- If they deflect, re-ask once with a different short phrasing."
    ),
    OnboardingStep.PERSONAL_INFO: (
        "- Prefer collecting city first, then region.\n"
        "- If city is unknown, ask for region only; re-ask once if unclear."
    ),
    OnboardingStep.FINANCIAL_SNAPSHOT: (
        "- Ask for goals first; avoid pressuring for income.\n"
        "- If they decline income, acknowledge and keep the question light on the next attempt."
    ),
    OnboardingStep.SOCIALS_OPTIN: (
        "- Ask a direct yes/no. If ambiguous, ask a clearer yes/no variant once."
    ),
    OnboardingStep.KB_EDUCATION: (
        "- Offer quick help; if they say no, acknowledge and proceed."
    ),
    OnboardingStep.STYLE_FINALIZE: (
        "- Briefly confirm inferred tone/verbosity in <= 1 sentence; do not ask any new personal questions."
    ),
    OnboardingStep.COMPLETION: (
        "- Summarize politely and end; do not ask follow-up questions."
    ),
}

NODE_OBJECTIVES: dict[OnboardingStep, str] = {
    OnboardingStep.GREETING: (
        "Node objective: Collect identity.preferred_name. "
        "Keep the conversation in this node until it is captured and acknowledged."
    ),
    OnboardingStep.LANGUAGE_TONE: (
        "Node objective: Collect only safety preferences: safety.blocked_categories and safety.allow_sensitive. "
        "Do not ask about tone or style here; tone will be inferred later. Stay until safety is resolved."
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
    OnboardingStep.STYLE_FINALIZE: (
        "Node objective: Infer style.{tone,verbosity,formality,emojis} and accessibility.{reading_level_hint,glossary_level_hint} "
        "from the overall conversation and briefly confirm. Do not ask for new personal or safety info here."
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
    rules = UNIT_RULES.get(step, "")
    return f"{base}\n{GUARDRAILS}\n{obj}\n{rules}"


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
            "Collect safety preferences only. Fields: safety.blocked_categories, safety.allow_sensitive. "
            f"Missing: {missing}. Ask one short yes/no or short answer question."
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
    if step == OnboardingStep.STYLE_FINALIZE:
        return (
            "Infer style and accessibility preferences from the conversation so far and briefly confirm. "
            "Do not ask for new personal or safety details."
        )
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
        "You are Vera, a warm, supportive financial coach. Keep replies concise, kind, "
        "and clear. Ask only ONE question at a time. Avoid assumptions. Use simple words.\n"
        "Craft the next message for the user given the context.\n"
        "- Be concise and warm\n"
        "- Ask only ONE question\n"
        "- Avoid repeating previously confirmed info\n"
        "Instruction: " + instruction + "\n"
        "context: " + str(ctx)
    )
    return system, user_prompt, {"user_context": ctx, "step": step.value}
