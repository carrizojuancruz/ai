from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from contextlib import suppress
from typing import Any

from langfuse.callback import CallbackHandler

from app.agents.onboarding.constants import (
    AGE_HESITATION_WORDS,
)
from app.agents.onboarding.prompts import DEFAULT_RESPONSE_BY_STEP, ONBOARDING_SYSTEM_PROMPT, STEP_GUIDANCE
from app.agents.onboarding.state import OnboardingState, OnboardingStep
from app.core.config import config
from app.services.llm import get_llm_client

from .context_patching import context_patching_service
from .interaction_choices import get_choices_for_field, should_always_offer_choices

logger = logging.getLogger(__name__)

langfuse_handler = CallbackHandler(
    public_key=config.LANGFUSE_PUBLIC_KEY,
    secret_key=config.LANGFUSE_SECRET_KEY,
    host=config.LANGFUSE_HOST,
)

ALLOWED_FIELDS_BY_STEP: dict[OnboardingStep, list[str]] = {
    OnboardingStep.WARMUP: ["warmup_choice"],
    OnboardingStep.IDENTITY: [
        "preferred_name",
        "age",
        "age_range",
        "location",
        "city",
        "region",
        "personal_goals",
    ],
    OnboardingStep.INCOME_MONEY: [
        "money_feelings",
        "annual_income",
        "annual_income_range",
        "income",
        "income_range",
        "personal_goals",
    ],
    OnboardingStep.ASSETS_EXPENSES: ["assets_types", "fixed_expenses"],
    OnboardingStep.HOME: ["housing_type", "housing_satisfaction", "monthly_housing_cost"],
    OnboardingStep.FAMILY_UNIT: ["dependents_under_18", "pets"],
    OnboardingStep.HEALTH_COVERAGE: ["health_insurance_status", "monthly_health_cost"],
    OnboardingStep.LEARNING_PATH: ["learning_interests"],
    OnboardingStep.PLAID_INTEGRATION: [],
    OnboardingStep.CHECKOUT_EXIT: ["final_choice"],
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
                "interaction_type": {
                    "type": "string",
                    "enum": ["free_text", "binary_choice", "single_choice", "multi_choice", "technical_integration"],
                },
                "choices": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "label": {"type": "string"},
                            "value": {"type": "string"},
                            "synonyms": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["id", "label", "value"],
                    },
                },
                "multi_min": {"type": "integer"},
                "multi_max": {"type": "integer"},
                "primary_choice": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "label": {"type": "string"},
                        "value": {"type": "string"},
                        "synonyms": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "secondary_choice": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "label": {"type": "string"},
                        "value": {"type": "string"},
                        "synonyms": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "required": [
                "assistant_text",
                "patch",
                "complete",
                "declined",
                "off_topic",
                "interaction_type",
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
                    "user_id": str(state.user_id),
                    "step": step.value,
                    "tags": ["onboarding", "verde-ai", f"step:{step.name}", "reason"],
                    "original_query": state.last_user_message or "",
                },
            )
            result = self._parse_llm_response(raw_response)
            result["patch"] = context_patching_service.normalize_patch_for_step(step, result.get("patch") or {})

            if state.last_user_message:
                msg_lower = state.last_user_message.lower()

                if step == OnboardingStep.IDENTITY and ("age_range" in missing_fields or "age" in missing_fields):
                    age_hesitation = any(word in msg_lower for word in AGE_HESITATION_WORDS) or msg_lower.strip() in {
                        "no"
                    }
                    if age_hesitation:
                        result["interaction_type"] = "single_choice"
                        result["patch"]["age_range"] = None
                        result["patch"].pop("age", None)

            if step == OnboardingStep.WARMUP:
                choice_info = get_choices_for_field("warmup_choice", step)
                if choice_info:
                    result["assistant_text"] = "Want to do a quick onboarding now or skip it?"
                    result["interaction_type"] = choice_info["type"]
                    result["choices"] = choice_info.get("choices", [])
                    result.pop("primary_choice", None)
                    result.pop("secondary_choice", None)
            else:
                if (result.get("interaction_type") == "free_text") and missing_fields:
                    for field in missing_fields:
                        if should_always_offer_choices(step, field):
                            choice_info = get_choices_for_field(field, step)
                            if choice_info:
                                result["interaction_type"] = choice_info["type"]
                                if choice_info["type"] == "binary_choice":
                                    result["primary_choice"] = choice_info.get("primary_choice")
                                    result["secondary_choice"] = choice_info.get("secondary_choice")
                                elif choice_info["type"] in ["single_choice", "multi_choice"]:
                                    result["choices"] = choice_info.get("choices", [])
                                    if choice_info["type"] == "multi_choice":
                                        result["multi_min"] = choice_info.get("multi_min", 1)
                                        result["multi_max"] = choice_info.get("multi_max", 3)
                                break

                if result.get("interaction_type") != "free_text" and missing_fields:
                    for field in missing_fields:
                        choice_info = get_choices_for_field(field, step)
                        if choice_info:
                            if choice_info["type"] == "binary_choice":
                                result["primary_choice"] = choice_info.get("primary_choice")
                                result["secondary_choice"] = choice_info.get("secondary_choice")
                            elif choice_info["type"] in ["single_choice", "multi_choice"]:
                                result["choices"] = choice_info.get("choices", [])
                                if choice_info["type"] == "multi_choice":
                                    result["multi_min"] = choice_info.get("multi_min", 1)
                                    result["multi_max"] = choice_info.get("multi_max", 3)
                            break

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

        text_prompt = self._build_text_prompt(
            step=step,
            missing_fields=missing_fields,
            last_user_message=state.last_user_message,
            convo_tail=convo_tail,
            state_dict=state_dict,
        )

        accumulated_text = ""
        try:
            with suppress(Exception):
                self._llm.set_callbacks([langfuse_handler])
            async for chunk in self._llm.generate_stream(
                prompt=text_prompt,
                system=ONBOARDING_SYSTEM_PROMPT
                + "\n\nGenerate only the conversational response text, no JSON or metadata.\n"
                + "Do NOT list or enumerate options/choices; the UI will present them. If offering choices, only invite selection briefly.",
                context={
                    "conversation_id": str(state.conversation_id),
                    "thread_id": str(state.conversation_id),
                    "user_id": str(state.user_id),
                    "step": step.value,
                    "tags": ["onboarding", "verde-ai", f"step:{step.name}", "text"],
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

            metadata_prompt = self._build_metadata_prompt(
                step=step,
                missing_fields=missing_fields,
                allowed_fields=allowed_fields,
                last_user_message=state.last_user_message,
                assistant_response=accumulated_text,
                state_dict=state_dict,
            )

            metadata_response = self._llm.generate(
                prompt=metadata_prompt,
                system="Extract structured data from the conversation. Output only valid JSON matching the schema.",
                context={
                    "conversation_id": str(state.conversation_id),
                    "thread_id": str(state.conversation_id),
                    "user_id": str(state.user_id),
                    "step": step.value,
                    "tags": ["onboarding", "verde-ai", f"step:{step.name}", "metadata"],
                },
            )

            result = self._parse_llm_response(metadata_response)
            result["assistant_text"] = accumulated_text
            result["patch"] = context_patching_service.normalize_patch_for_step(step, result.get("patch") or {})
            result["streaming"] = False

            if state.last_user_message:
                msg_lower = state.last_user_message.lower()

                if step == OnboardingStep.IDENTITY and ("age_range" in missing_fields or "age" in missing_fields):
                    age_hesitation = any(word in msg_lower for word in AGE_HESITATION_WORDS) or msg_lower.strip() in {
                        "no"
                    }
                    if age_hesitation:
                        result["interaction_type"] = "single_choice"
                        result["patch"]["age_range"] = None
                        result["patch"].pop("age", None)

            if (result.get("interaction_type") == "free_text") and missing_fields:
                for field in missing_fields:
                    if should_always_offer_choices(step, field):
                        choice_info = get_choices_for_field(field, step)
                        if choice_info:
                            result["interaction_type"] = choice_info["type"]
                            if choice_info["type"] == "binary_choice":
                                result["primary_choice"] = choice_info.get("primary_choice")
                                result["secondary_choice"] = choice_info.get("secondary_choice")
                            elif choice_info["type"] in ["single_choice", "multi_choice"]:
                                result["choices"] = choice_info.get("choices", [])
                                if choice_info["type"] == "multi_choice":
                                    result["multi_min"] = choice_info.get("multi_min", 1)
                                    result["multi_max"] = choice_info.get("multi_max", 3)
                            break

            if result.get("interaction_type") != "free_text" and missing_fields:
                for field in missing_fields:
                    choice_info = get_choices_for_field(field, step)
                    if choice_info:
                        if choice_info["type"] == "binary_choice":
                            result["primary_choice"] = choice_info.get("primary_choice")
                            result["secondary_choice"] = choice_info.get("secondary_choice")
                        elif choice_info["type"] in ["single_choice", "multi_choice"]:
                            result["choices"] = choice_info.get("choices", [])
                            if choice_info["type"] == "multi_choice":
                                result["multi_min"] = choice_info.get("multi_min", 1)
                                result["multi_max"] = choice_info.get("multi_max", 3)
                        break

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

        available_choices = {}
        for field in missing_fields:
            choice_info = get_choices_for_field(field, step)
            if choice_info:
                available_choices[field] = choice_info

        instructions = (
            ((step_guidance + "\n") if step_guidance else "")
            + "You are conducting an onboarding conversation. Analyze the user's response to determine the best interaction type.\n\n"
            "INTERACTION TYPE DECISION FRAMEWORK:\n\n"
            "1. Use 'free_text' when:\n"
            "   - User provides a direct, specific answer (e.g., 'I'm 28', 'I make $50k')\n"
            "   - User seems comfortable and confident in their response\n"
            "   - User provides detailed information voluntarily\n"
            "   - The field is open-ended and doesn't have predefined options\n\n"
            "2. Switch to choice-based interactions when:\n"
            "   - User expresses ANY form of hesitation or uncertainty\n"
            "   - User asks for help in any way (e.g., 'what should I say?', 'I'm not sure', 'can you help?')\n"
            "   - User requests structure (e.g., mentions 'options', 'choices', 'ranges', 'categories', 'examples')\n"
            "   - User prefers not to be specific (e.g., 'around...', 'approximately...', 'somewhere between...')\n"
            "   - User shows discomfort with exact values (e.g., 'I'd rather not say exactly', 'is a range ok?')\n"
            "   - User's response is vague or unclear\n"
            "   - User references previous interactions where choices were given\n"
            "   - User seems to be asking what format you want the answer in\n\n"
            "3. Critical Context Signals:\n"
            "   - Questions about format = wants choices\n"
            "   - Comparison or reference to previous steps = wants consistency\n"
            "   - Any form of 'help me decide' = needs choices\n"
            "   - Uncertainty markers ('maybe', 'possibly', 'I think') = offer choices\n\n"
            "FIELD-SPECIFIC GUIDANCE:\n"
        )

        if "age" in missing_fields or "age_range" in missing_fields:
            instructions += "- Age: If user shows ANY hesitation about exact age, use single_choice with age ranges\n"

        if any(f in missing_fields for f in ["income", "income_range", "annual_income", "annual_income_range"]):
            instructions += (
                "- Income: Sensitive topic - if ANY discomfort detected, offer income ranges via single_choice\n"
            )

        if "money_feelings" in missing_fields:
            instructions += "- Money Feelings: This is subjective - strongly consider multi_choice to help user articulate emotions\n"

        if "learning_interests" in missing_fields:
            instructions += "- Learning Interests: Always use multi_choice - users benefit from seeing topic options\n"

        always_choice_fields = []
        for field in missing_fields:
            if should_always_offer_choices(step, field):
                always_choice_fields.append(field)

        if always_choice_fields:
            instructions += (
                f"\n⚠️ MANDATORY CHOICE FIELDS: {', '.join(always_choice_fields)} - MUST use appropriate choice type\n"
            )

        instructions += "\nAvailable choice configurations:\n"
        for field, choice_info in available_choices.items():
            instructions += f"- {field}: {choice_info['type']} available"
            if choice_info["type"] == "multi_choice":
                instructions += f" (min: {choice_info.get('multi_min', 1)}, max: {choice_info.get('multi_max', 3)})"
            instructions += "\n"

        instructions += (
            "\n\nRESPONSE RULES:\n"
            "- Naturally acknowledge the user's communication style\n"
            "- When offering choices, don't list them in text - just invite selection\n"
            "- Adapt your tone to match the user's comfort level\n"
            "- For binary_choice: use primary_choice and secondary_choice fields\n"
            "- For single/multi_choice: use the choices array\n"
            "- The UI will display the actual options - you just set up the interaction type\n"
            "- Trust your analysis of user intent over literal words\n"
            "- Output ONLY valid JSON matching the schema\n\n"
            f"Current Step: {step.value}\n"
            f"Missing fields: {missing_fields}\n"
            f"Allowed patch fields: {allowed_fields}\n"
            f"User's message: {last_user_message or '[No message]'}\n"
            f"Recent conversation:\n{convo_tail}\n"
            f"User context: {json.dumps(state_dict, ensure_ascii=False)}\n"
            f"Required JSON Schema: {json.dumps(self._json_schema, ensure_ascii=False)}\n"
        )
        return instructions

    def _parse_llm_response(self, raw_response: str) -> dict[str, Any]:
        try:
            result = json.loads(raw_response)
        except Exception:
            start = raw_response.find("{")
            end = raw_response.rfind("}")
            result = json.loads(raw_response[start : end + 1]) if start != -1 and end != -1 and end > start else {}
        if not isinstance(result, dict):
            result = {}
        result.setdefault("assistant_text", "")
        result.setdefault("patch", {})
        result.setdefault("complete", False)
        result.setdefault("declined", False)
        result.setdefault("off_topic", False)
        result.setdefault("memory_candidates", [])
        result.setdefault("interaction_type", "free_text")
        return result

    def _default_response(self) -> dict[str, Any]:
        return {
            "assistant_text": "",
            "patch": {},
            "complete": False,
            "declined": False,
            "off_topic": False,
            "memory_candidates": [],
            "interaction_type": "free_text",
        }

    def _build_context_summary(self, state_dict: dict[str, Any]) -> str:
        lines: list[str] = []
        max_lines = 12
        max_depth = 2
        max_list_items = 3

        def add_line(key: str, value: Any) -> None:
            nonlocal lines
            if len(lines) >= max_lines:
                return
            if isinstance(value, str):
                val = value.strip()
                if not val:
                    return
                if len(val) > 80:
                    val = val[:77] + "..."
                lines.append(f"{key}: {val}")
            elif isinstance(value, (int, float, bool)):
                lines.append(f"{key}: {value}")
            elif isinstance(value, list):
                if not value:
                    return
                items: list[str] = []
                for item in value[:max_list_items]:
                    if isinstance(item, (str, int, float, bool)):
                        item_str = str(item)
                        if len(item_str) > 40:
                            item_str = item_str[:37] + "..."
                        items.append(item_str)
                if items:
                    suffix = f" (+{len(value) - len(items)} more)" if len(value) > len(items) else ""
                    lines.append(f"{key}: {', '.join(items)}{suffix}")

        def walk(d: dict[str, Any], prefix: str = "", depth: int = 0) -> None:
            if depth > max_depth or len(lines) >= max_lines:
                return
            if not isinstance(d, dict):
                return
            for k, v in d.items():
                path = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
                if v in (None, "", [], {}):
                    continue
                if isinstance(v, (str, int, float, bool, list)):
                    add_line(path, v)
                elif isinstance(v, dict):
                    walk(v, path, depth + 1)

        walk(state_dict, "", 0)
        return "\n".join(lines) if lines else "(none)"

    def _build_text_prompt(
        self,
        step: OnboardingStep,
        missing_fields: list[str],
        last_user_message: str | None,
        convo_tail: str,
        state_dict: dict[str, Any],
    ) -> str:
        step_guidance = STEP_GUIDANCE.get(step, "")
        default_prompt = DEFAULT_RESPONSE_BY_STEP.get(step, "")

        ctx_block = self._build_context_summary(state_dict)

        prompt = f"""Current step: {step.value}

{step_guidance}

Missing information: {", ".join(missing_fields) if missing_fields else "None"}
User's last message: {last_user_message or "(Starting conversation)"}

Known user context (short):
{ctx_block}

Recent conversation (most recent last):
{convo_tail}

Respond naturally and conversationally. Default prompt if needed: "{default_prompt}"

Important UI rules:
- Do NOT list or enumerate options/choices in your message. The UI will present them separately.
- If offering choices, simply invite selection in 1–2 sentences (no bullets or lists).
- Always respond to the 'User's last message' shown above; avoid referencing earlier turns unless necessary for clarity.
"""
        return prompt

    def _build_metadata_prompt(
        self,
        step: OnboardingStep,
        missing_fields: list[str],
        allowed_fields: list[str],
        last_user_message: str | None,
        assistant_response: str,
        state_dict: dict[str, Any],
    ) -> str:
        return f"""Extract structured data from this conversation:

Step: {step.value}
User message: {last_user_message or ""}
Assistant response: {assistant_response}
Missing fields: {missing_fields}
Allowed patch fields: {allowed_fields}

Current user context: {json.dumps(state_dict, ensure_ascii=False)}

Output JSON matching this schema: {json.dumps(self._json_schema, ensure_ascii=False)}

Rules:
- Extract any new information the user provided
- Map to allowed fields using dot notation
- Set complete=true if step requirements are met
- Set declined=true if user explicitly declines
- Leave patch empty if no new information provided
"""


onboarding_reasoning_service = OnboardingReasoningService()
