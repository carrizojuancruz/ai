from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import suppress
from typing import Any

from langfuse.callback import CallbackHandler

from app.agents.onboarding.prompts import ONBOARDING_SYSTEM_PROMPT, STEP_GUIDANCE
from app.agents.onboarding.state import OnboardingState, OnboardingStep
from app.services.llm.client import get_llm_client

from .context_patching import context_patching_service

logger = logging.getLogger(__name__)

langfuse_handler = CallbackHandler(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST"),
)

ALLOWED_FIELDS_BY_STEP: dict[OnboardingStep, list[str]] = {
    OnboardingStep.GREETING: ["identity.preferred_name"],
    OnboardingStep.LANGUAGE_TONE: [
        "safety.blocked_categories",
        "safety.allow_sensitive",
    ],
    OnboardingStep.MOOD_CHECK: ["mood"],
    OnboardingStep.PERSONAL_INFO: ["location.city", "location.region"],
    OnboardingStep.FINANCIAL_SNAPSHOT: ["goals", "income", "primary_financial_goal"],
    OnboardingStep.SOCIALS_OPTIN: ["social_signals_consent", "opt_in"],
    OnboardingStep.KB_EDUCATION: [],
    OnboardingStep.STYLE_FINALIZE: [
        "style.tone",
        "style.verbosity",
        "style.formality",
        "style.emojis",
        "accessibility.reading_level_hint",
        "accessibility.glossary_level_hint",
    ],
    OnboardingStep.COMPLETION: [],
}


class OnboardingReasoningService:
    def __init__(self) -> None:
        self._llm = get_llm_client()
        self._json_schema = {
            "type": "object",
            "properties": {
                "assistant_text": {"type": "string"},
                "patch": {"type": "object"},
                "complete": {"type": "boolean"},
                "declined": {"type": "boolean"},
                "off_topic": {"type": "boolean"},
                "memory_candidates": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "assistant_text",
                "patch",
                "complete",
                "declined",
                "off_topic",
            ],
            "additionalProperties": False,
        }

    def reason_step(self, state: OnboardingState, step: OnboardingStep, missing_fields: list[str]) -> dict[str, Any]:
        allowed_fields = ALLOWED_FIELDS_BY_STEP.get(step, [])
        state_dict = state.user_context.model_dump(mode="json")
        convo_tail = self._build_conversation_context(state.conversation_history)
        user_instructions = self._build_user_instructions(
            step=step,
            missing_fields=missing_fields,
            allowed_fields=allowed_fields,
            last_user_message=state.last_user_message,
            convo_tail=convo_tail,
            state_dict=state_dict,
        )
        try:
            with suppress(Exception):
                self._llm.set_callbacks([langfuse_handler])
            raw_response = self._llm.generate(
                prompt=user_instructions,
                system=ONBOARDING_SYSTEM_PROMPT,
                context={
                    "conversation_id": str(state.conversation_id),
                    "thread_id": str(state.conversation_id),
                    "step": step.value,
                    "tags": ["onboarding", "verde-ai", f"step:{step.name}", "reason"],
                    "original_query": state.last_user_message or "",
                },
            )
            result = self._parse_llm_response(raw_response)
            result["patch"] = context_patching_service.normalize_patch_for_step(step, result.get("patch") or {})
            return result
        except Exception as e:
            logger.error("LLM reason failed: %s", e)
            return self._default_response()

    async def reason_step_stream(
        self, state: OnboardingState, step: OnboardingStep, missing_fields: list[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        allowed_fields = ALLOWED_FIELDS_BY_STEP.get(step, [])
        state_dict = state.user_context.model_dump(mode="json")
        convo_tail = self._build_conversation_context(state.conversation_history)
        user_instructions = self._build_user_instructions(
            step=step,
            missing_fields=missing_fields,
            allowed_fields=allowed_fields,
            last_user_message=state.last_user_message,
            convo_tail=convo_tail,
            state_dict=state_dict,
        )
        accumulated_text = ""
        try:
            async for chunk in self._llm.generate_stream(
                prompt=user_instructions,
                system=ONBOARDING_SYSTEM_PROMPT,
                context={
                    "conversation_id": str(state.conversation_id),
                    "thread_id": str(state.conversation_id),
                    "step": step.value,
                    "tags": ["onboarding", "verde-ai", f"step:{step.name}", "reason"],
                    "original_query": state.last_user_message or "",
                },
            ):
                accumulated_text += chunk
                yield {
                    "assistant_text": accumulated_text,
                    "patch": {},
                    "complete": False,
                    "declined": False,
                    "off_topic": False,
                    "memory_candidates": [],
                    "streaming": True,
                    "chunk": chunk,
                }
            result = self._parse_llm_response(accumulated_text)
            result["patch"] = context_patching_service.normalize_patch_for_step(step, result.get("patch") or {})
            result["streaming"] = False
            yield result
        except Exception as e:
            logger.error("LLM reason stream failed: %s", e)
            yield self._default_response()

    def _build_conversation_context(self, conversation_history: list[dict[str, Any]]) -> str:
        return "\n".join(
            f"U:{turn.get('user_message', '')}\nA:{turn.get('agent_response', '')}"
            for turn in conversation_history[-6:]
        )

    def _build_user_instructions(
        self,
        step: OnboardingStep,
        missing_fields: list[str],
        allowed_fields: list[str],
        last_user_message: str | None,
        convo_tail: str,
        state_dict: dict[str, Any],
    ) -> str:
        step_guidance = STEP_GUIDANCE.get(step, "")
        instructions = (
            ((step_guidance + "\n") if step_guidance else "") + "Follow these rules strictly:\n"
            "- Use Allowed patch fields exactly (map synonyms like 'preferred_name'/'city' to canonical dot-paths).\n"
            "- If the user explicitly declines this field, set declined=true and keep assistant_text concise.\n"
            "- If off-topic, set off_topic=true and assistant_text should briefly acknowledge then pivot back.\n"
            "- Output ONLY JSON for the schema.\n"
            f"Step: {step.value}\n"
            f"Missing fields: {missing_fields}\n"
            f"Allowed patch fields: {allowed_fields}\n"
            f"Last user message: {last_user_message or ''}\n"
            f"Recent conversation (most recent last):\n{convo_tail}\n"
            f"Context: {json.dumps(state_dict, ensure_ascii=False)}\n"
            f"JSON Schema: {json.dumps(self._json_schema, ensure_ascii=False)}\n"
        )
        return instructions

    def _parse_llm_response(self, raw_response: str) -> dict[str, Any]:
        try:
            result = json.loads(raw_response)
        except Exception:
            start = raw_response.find("{")
            end = raw_response.rfind("}")
            if start != -1 and end != -1 and end > start:
                result = json.loads(raw_response[start : end + 1])
            else:
                result = {}
        if not isinstance(result, dict):
            result = {}
        result.setdefault("assistant_text", "")
        result.setdefault("patch", {})
        result.setdefault("complete", False)
        result.setdefault("declined", False)
        result.setdefault("off_topic", False)
        result.setdefault("memory_candidates", [])
        return result

    def _default_response(self) -> dict[str, Any]:
        return {
            "assistant_text": "",
            "patch": {},
            "complete": False,
            "declined": False,
            "off_topic": False,
            "memory_candidates": [],
        }


onboarding_reasoning_service = OnboardingReasoningService()
