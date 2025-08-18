"""Onboarding agent powered by a LangGraph StateGraph (one node per step).

Each node delegates to a single LLM "reasoner" call that:
- Crafts the next assistant message (assistant_text)
- Returns a context patch (canonical dot-paths) for the step’s fields
- Signals completion/decline/off-topic flags

Handlers apply the patch safely into `user_context`, advance when complete,
record the turn, and then the compiled graph is invoked per message.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage
from langfuse.callback import CallbackHandler
from langgraph.graph import END, StateGraph

from app.models import MemoryCategory

from .state import OnboardingState, OnboardingStep

langfuse_handler = CallbackHandler(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST"),
)

logger = logging.getLogger(__name__)

STEP_GUIDANCE: dict[OnboardingStep, str] = {
    OnboardingStep.GREETING: (
        "Goal: learn the user's preferred name. Ask ONE short, friendly question. "
        "If they provide a name, confirm lightly. If they decline, acknowledge and move on."
    ),
    OnboardingStep.LANGUAGE_TONE: (
        "Goal: capture safety preferences only. Target fields: safety.blocked_categories, safety.allow_sensitive. "
        "Ask if any topics to avoid (accept 'none'), and whether discussing sensitive finance is okay (yes/no)."
    ),
    OnboardingStep.MOOD_CHECK: (
        "Goal: get a short mood about money today. Ask for a few words only; be empathetic."
    ),
    OnboardingStep.PERSONAL_INFO: (
        "Goal: capture location.city and location.region. If one is known, ask only for the other. "
        "Keep it to ONE question at a time."
    ),
    OnboardingStep.FINANCIAL_SNAPSHOT: (
        "Goal: capture goals (short list) and income band (rough). Ask for ONE at a time; "
        "summarize goals in short phrases."
    ),
    OnboardingStep.SOCIALS_OPTIN: (
        "Goal: ask a single yes/no about opting in to social signals. Map response to a boolean."
    ),
    OnboardingStep.KB_EDUCATION: (
        "Goal: offer quick help from the knowledge base before wrapping; keep it brief and optional."
    ),
    OnboardingStep.STYLE_FINALIZE: (
        "Goal: infer and/or confirm style.{tone,verbosity,formality,emojis} and "
        "accessibility.{reading_level_hint,glossary_level_hint} from the conversation so far."
    ),
    OnboardingStep.COMPLETION: (
        "Goal: confirm onboarding is complete and set readiness to proceed to main chat."
    ),
}

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

if not (
    os.getenv("LANGFUSE_PUBLIC_KEY")
    and os.getenv("LANGFUSE_SECRET_KEY")
    and os.getenv("LANGFUSE_HOST")
):
    logger.warning(
        "Langfuse env vars missing or incomplete; callback tracing will be disabled"
    )


class OnboardingAgent:
    """Onboarding Agent implementing node-per-step logic with LLM prompts."""

    def __init__(self) -> None:
        self.graph = self._create_graph()
        self._chat_bedrock = None

    def _ensure_bedrock_chat(self) -> None:
        if self._chat_bedrock is not None:
            return
        try:
            provider = os.getenv("LLM_PROVIDER", "").strip().lower()
            if provider != "bedrock":
                raise RuntimeError(
                    "LLM_PROVIDER must be 'bedrock' to enable LangChain Bedrock callbacks"
                )
            region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
            model_id = os.getenv(
                "BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"
            )
            if not region:
                raise RuntimeError(
                    "AWS_REGION or AWS_DEFAULT_REGION must be set for Bedrock"
                )
            from langchain_aws import ChatBedrock

            self._chat_bedrock = ChatBedrock(
                model_id=model_id,
                region_name=region,
            )
            logger.info(
                "ChatBedrock initialized (model_id=%s, region=%s)", model_id, region
            )
        except Exception as e:
            logger.error("Failed to initialize ChatBedrock: %s", e)
            raise

    def _create_graph(self) -> StateGraph:
        workflow = StateGraph(OnboardingState)

        for name in [
            "greeting",
            "language_tone",
            "mood_check",
            "personal_info",
            "financial_snapshot",
            "socials_optin",
            "kb_education",
            "style_finalize",
            "completion",
        ]:
            workflow.add_node(name, getattr(self, f"_handle_{name}"))

        def _router_identity(state: OnboardingState) -> OnboardingState:
            return state

        def route_by_current_step(state: OnboardingState) -> str:
            return state.current_step.value

        workflow.add_node("route", _router_identity)
        workflow.add_conditional_edges(
            "route",
            route_by_current_step,
            {
                "greeting": "greeting",
                "language_tone": "language_tone",
                "mood_check": "mood_check",
                "personal_info": "personal_info",
                "financial_snapshot": "financial_snapshot",
                "socials_optin": "socials_optin",
                "kb_education": "kb_education",
                "style_finalize": "style_finalize",
                "completion": "completion",
            },
        )

        for name in [
            "greeting",
            "language_tone",
            "mood_check",
            "personal_info",
            "financial_snapshot",
            "socials_optin",
            "kb_education",
            "style_finalize",
            "completion",
        ]:
            workflow.add_edge(name, END)

        workflow.set_entry_point("route")
        return workflow.compile()

    def _to_text(self, content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict) and "text" in block:
                    parts.append(str(block.get("text") or ""))
                else:
                    parts.append(str(block))
            return "".join(parts)
        if isinstance(content, dict):
            if "text" in content:
                return str(content.get("text") or "")
            if "content" in content:
                return self._to_text(content.get("content"))
        return str(content)

    # --- LLM-driven step reasoner and patcher ---
    def _normalize_patch_for_step(
        self, step: OnboardingStep, patch: dict[str, Any]
    ) -> dict[str, Any]:
        if not isinstance(patch, dict):
            return {}
        normalized: dict[str, Any] = {}
        for k, v in patch.items():
            key = k
            if step == OnboardingStep.GREETING:
                if k == "preferred_name":
                    key = "identity.preferred_name"
            elif step == OnboardingStep.LANGUAGE_TONE:
                if k == "blocked_categories":
                    key = "safety.blocked_categories"
                if k == "allow_sensitive":
                    key = "safety.allow_sensitive"
            elif step == OnboardingStep.PERSONAL_INFO:
                if k == "city":
                    key = "location.city"
                if k == "region":
                    key = "location.region"
            elif step == OnboardingStep.SOCIALS_OPTIN:
                if k == "opt_in":
                    key = "social_signals_consent"
            elif step == OnboardingStep.STYLE_FINALIZE:
                if k in {"tone", "verbosity", "formality", "emojis"}:
                    key = f"style.{k}"
                if k in {"reading_level_hint", "glossary_level_hint"}:
                    key = f"accessibility.{k}"
            normalized[key] = v
        return normalized

    def _apply_context_patch(
        self, state: OnboardingState, step: OnboardingStep, patch: dict[str, Any]
    ) -> None:
        if not patch:
            return

        def set_by_path(obj: Any, path: str, value: Any) -> None:
            parts = [p for p in path.split(".") if p]
            if not parts:
                return
            target = obj
            for idx, part in enumerate(parts):
                is_last = idx == len(parts) - 1
                if is_last:
                    try:
                        current_val = getattr(target, part, None)
                        if isinstance(current_val, list) and not isinstance(
                            value, list
                        ):
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

        normalized_patch = self._normalize_patch_for_step(step, patch)
        for key, value in normalized_patch.items():
            if "." in key:
                set_by_path(state.user_context, key, value)
            else:
                try:
                    if hasattr(state.user_context, key):
                        current_attr = getattr(state.user_context, key)
                        if isinstance(current_attr, list) and not isinstance(
                            value, list
                        ):
                            setattr(state.user_context, key, [value])
                        elif isinstance(value, dict):
                            for inner_key, inner_val in value.items():
                                set_by_path(
                                    state.user_context, f"{key}.{inner_key}", inner_val
                                )
                        else:
                            setattr(state.user_context, key, value)
                    else:
                        if key == "opt_in":
                            set_by_path(
                                state.user_context,
                                "social_signals_consent",
                                bool(value),
                            )
                except Exception:
                    pass

        with suppress(Exception):
            state.user_context.sync_nested_to_flat()

    def _reason_step(
        self, state: OnboardingState, step: OnboardingStep, missing: list[str]
    ) -> dict[str, Any]:
        self._ensure_bedrock_chat()
        allowed_fields = ALLOWED_FIELDS_BY_STEP.get(step, [])

        system = (
            "You are Vera's Onboarding Step Manager. Decide if the current step is complete, "
            "handle off-topic or declines gracefully, and produce the assistant's next short reply. "
            "Ask only ONE question at a time. Keep messages to 1-2 short sentences."
        )

        state_dict = state.user_context.model_dump(mode="json")
        convo_tail = "\n".join(
            f"U:{t.get('user_message', '')}\nA:{t.get('agent_response', '')}"
            for t in state.conversation_history[-6:]
        )

        json_schema = {
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

        step_guidance = STEP_GUIDANCE.get(step, "")

        user_instructions = ((step_guidance + "\n") if step_guidance else "") + (
            "Follow these rules strictly:\n"
            "- Use Allowed patch fields exactly (map synonyms like 'preferred_name'/'city' to canonical dot-paths).\n"
            "- If the user explicitly declines this field, set declined=true and keep assistant_text concise.\n"
            "- If off-topic, set off_topic=true and assistant_text should briefly acknowledge then pivot back.\n"
            "- Output ONLY JSON for the schema.\n"
            f"Step: {step.value}\n"
            f"Missing fields: {missing}\n"
            f"Allowed patch fields: {allowed_fields}\n"
            f"Last user message: {state.last_user_message or ''}\n"
            f"Recent conversation (most recent last):\n{convo_tail}\n"
            f"Context: {json.dumps(state_dict, ensure_ascii=False)}\n"
            f"JSON Schema: {json.dumps(json_schema, ensure_ascii=False)}\n"
        )

        messages = [
            SystemMessage(content=system),
            HumanMessage(content=user_instructions),
        ]

        try:
            resp = self._chat_bedrock.invoke(
                messages,
                config={
                    "callbacks": [langfuse_handler],
                    "thread_id": str(state.conversation_id),
                    "tags": ["onboarding", "verde-ai", f"step:{step.name}", "reason"],
                    "configurable": {
                        "session_id": str(state.conversation_id),
                        "original_query": state.last_user_message or "",
                    },
                },
            )
            raw = self._to_text(getattr(resp, "content", resp))
            try:
                result = json.loads(raw)
            except Exception:
                start = raw.find("{")
                end = raw.rfind("}")
                result = (
                    json.loads(raw[start : end + 1])
                    if start != -1 and end != -1 and end > start
                    else {}
                )

            if not isinstance(result, dict):
                result = {}
            result.setdefault("assistant_text", "")
            result.setdefault("patch", {})
            result.setdefault("complete", False)
            result.setdefault("declined", False)
            result.setdefault("off_topic", False)
            result.setdefault("memory_candidates", [])
            result["patch"] = self._normalize_patch_for_step(
                step, result.get("patch") or {}
            )
            return result
        except Exception as e:
            logger.error("Bedrock reason failed: %s", e)
            return {
                "assistant_text": "",
                "patch": {},
                "complete": False,
                "declined": False,
                "off_topic": False,
                "memory_candidates": [],
            }

    # --- Step completion checks (fallback if model didn't set 'complete') ---
    def _is_step_complete(self, state: OnboardingState, step: OnboardingStep) -> bool:
        try:
            if step == OnboardingStep.GREETING:
                return bool(state.user_context.identity.preferred_name)
            if step == OnboardingStep.LANGUAGE_TONE:
                return (
                    state.user_context.safety.blocked_categories is not None
                    and isinstance(state.user_context.safety.allow_sensitive, bool)
                )
            if step == OnboardingStep.MOOD_CHECK:
                return any(
                    getattr(m, "metadata", {}).get("type") == "mood"
                    for m in state.semantic_memories
                )
            if step == OnboardingStep.PERSONAL_INFO:
                return bool(
                    state.user_context.location.city
                    and state.user_context.location.region
                )
            if step == OnboardingStep.FINANCIAL_SNAPSHOT:
                return bool(state.user_context.goals and state.user_context.income)
            if step == OnboardingStep.SOCIALS_OPTIN:
                return isinstance(state.user_context.social_signals_consent, bool)
            if step == OnboardingStep.KB_EDUCATION:
                return True
            if step == OnboardingStep.STYLE_FINALIZE:
                return True
            if step == OnboardingStep.COMPLETION:
                return True
        except Exception:
            return False
        return False

    # --- Step handlers (LLM-driven, minimal logic) ---
    async def _handle_greeting(self, state: OnboardingState) -> OnboardingState:
        state.current_step = OnboardingStep.GREETING
        missing: list[str] = []
        if not state.user_context.identity.preferred_name:
            missing.append("identity.preferred_name")
        decision = self._reason_step(state, OnboardingStep.GREETING, missing)
        self._apply_context_patch(
            state, OnboardingStep.GREETING, decision.get("patch") or {}
        )
        if decision.get("assistant_text"):
            response = decision["assistant_text"]
        else:
            response = "Nice to meet you! What should I call you?"
        if decision.get("complete") or self._is_step_complete(
            state, OnboardingStep.GREETING
        ):
            state.mark_step_completed(OnboardingStep.GREETING)
            state.current_step = state.get_next_step() or OnboardingStep.LANGUAGE_TONE
        state.add_conversation_turn(state.last_user_message or "", response)
        return state

    async def _handle_language_tone(self, state: OnboardingState) -> OnboardingState:
        state.current_step = OnboardingStep.LANGUAGE_TONE
        if state.user_context.safety.blocked_categories is None:
            state.user_context.safety.blocked_categories = []
        missing: list[str] = []
        if not state.user_context.safety.blocked_categories:
            missing.append("safety.blocked_categories")
        if state.user_context.safety.allow_sensitive is None:
            missing.append("safety.allow_sensitive")
        decision = self._reason_step(state, OnboardingStep.LANGUAGE_TONE, missing)
        self._apply_context_patch(
            state, OnboardingStep.LANGUAGE_TONE, decision.get("patch") or {}
        )
        response = (
            decision.get("assistant_text")
            or "Any topics you’d prefer I avoid? And is it ok if I cover sensitive financial topics when helpful?"
        )
        if decision.get("complete") or self._is_step_complete(
            state, OnboardingStep.LANGUAGE_TONE
        ):
            state.mark_step_completed(OnboardingStep.LANGUAGE_TONE)
            state.current_step = state.get_next_step() or OnboardingStep.MOOD_CHECK
        state.add_conversation_turn(state.last_user_message or "", response)
        return state

    async def _handle_mood_check(self, state: OnboardingState) -> OnboardingState:
        state.current_step = OnboardingStep.MOOD_CHECK
        decision = self._reason_step(state, OnboardingStep.MOOD_CHECK, ["mood"])
        mood_val = (decision.get("patch") or {}).get("mood")
        if mood_val:
            state.add_semantic_memory(
                content=f"User's current mood about money: {mood_val}",
                category=MemoryCategory.PERSONAL,
                metadata={"type": "mood", "value": mood_val, "context": "money"},
            )
        response = (
            decision.get("assistant_text") or "How are you feeling about money today?"
        )
        if decision.get("complete") or self._is_step_complete(
            state, OnboardingStep.MOOD_CHECK
        ):
            state.mark_step_completed(OnboardingStep.MOOD_CHECK)
            state.current_step = state.get_next_step() or OnboardingStep.PERSONAL_INFO
        state.add_conversation_turn(state.last_user_message or "", response)
        return state

    async def _handle_personal_info(self, state: OnboardingState) -> OnboardingState:
        state.current_step = OnboardingStep.PERSONAL_INFO
        missing: list[str] = []
        if not state.user_context.location.city:
            missing.append("location.city")
        if not state.user_context.location.region:
            missing.append("location.region")
        decision = self._reason_step(state, OnboardingStep.PERSONAL_INFO, missing)
        self._apply_context_patch(
            state, OnboardingStep.PERSONAL_INFO, decision.get("patch") or {}
        )
        response = decision.get("assistant_text") or "What city and region are you in?"
        if decision.get("complete") or self._is_step_complete(
            state, OnboardingStep.PERSONAL_INFO
        ):
            state.mark_step_completed(OnboardingStep.PERSONAL_INFO)
            state.current_step = (
                state.get_next_step() or OnboardingStep.FINANCIAL_SNAPSHOT
            )
        state.add_conversation_turn(state.last_user_message or "", response)
        return state

    async def _handle_financial_snapshot(
        self, state: OnboardingState
    ) -> OnboardingState:
        state.current_step = OnboardingStep.FINANCIAL_SNAPSHOT
        missing: list[str] = []
        if not state.user_context.goals:
            missing.append("goals")
        if not state.user_context.income:
            missing.append("income")
        decision = self._reason_step(state, OnboardingStep.FINANCIAL_SNAPSHOT, missing)
        self._apply_context_patch(
            state, OnboardingStep.FINANCIAL_SNAPSHOT, decision.get("patch") or {}
        )
        response = (
            decision.get("assistant_text")
            or "What money goals are on your mind, and roughly what’s your income band?"
        )
        if decision.get("complete") or self._is_step_complete(
            state, OnboardingStep.FINANCIAL_SNAPSHOT
        ):
            state.mark_step_completed(OnboardingStep.FINANCIAL_SNAPSHOT)
            state.current_step = state.get_next_step() or OnboardingStep.SOCIALS_OPTIN
        state.add_conversation_turn(state.last_user_message or "", response)
        return state

    async def _handle_socials_optin(self, state: OnboardingState) -> OnboardingState:
        state.current_step = OnboardingStep.SOCIALS_OPTIN
        decision = self._reason_step(state, OnboardingStep.SOCIALS_OPTIN, [])
        self._apply_context_patch(
            state, OnboardingStep.SOCIALS_OPTIN, decision.get("patch") or {}
        )
        response = (
            decision.get("assistant_text")
            or "Would you like me to use social signals to personalize your experience?"
        )
        if decision.get("complete") or self._is_step_complete(
            state, OnboardingStep.SOCIALS_OPTIN
        ):
            state.mark_step_completed(OnboardingStep.SOCIALS_OPTIN)
            state.current_step = state.get_next_step() or OnboardingStep.KB_EDUCATION
        state.add_conversation_turn(state.last_user_message or "", response)
        return state

    async def _handle_kb_education(self, state: OnboardingState) -> OnboardingState:
        state.current_step = OnboardingStep.KB_EDUCATION
        decision = self._reason_step(state, OnboardingStep.KB_EDUCATION, [])
        response = (
            decision.get("assistant_text")
            or "Anything you’d like quick help with from our knowledge base before we wrap?"
        )
        state.mark_step_completed(OnboardingStep.KB_EDUCATION)
        state.current_step = state.get_next_step() or OnboardingStep.STYLE_FINALIZE
        state.add_conversation_turn(state.last_user_message or "", response)
        return state

    async def _handle_style_finalize(self, state: OnboardingState) -> OnboardingState:
        state.current_step = OnboardingStep.STYLE_FINALIZE
        decision = self._reason_step(state, OnboardingStep.STYLE_FINALIZE, [])
        self._apply_context_patch(
            state, OnboardingStep.STYLE_FINALIZE, decision.get("patch") or {}
        )
        response = (
            decision.get("assistant_text")
            or "I’ll keep replies clear and friendly. Sound good?"
        )
        state.add_conversation_turn(state.last_user_message or "", response)
        state.mark_step_completed(OnboardingStep.STYLE_FINALIZE)
        state.current_step = state.get_next_step() or OnboardingStep.COMPLETION
        return state

    async def _handle_completion(self, state: OnboardingState) -> OnboardingState:
        state.current_step = OnboardingStep.COMPLETION
        decision = self._reason_step(state, OnboardingStep.COMPLETION, [])
        response = (
            decision.get("assistant_text") or "All set! You’re ready to start chatting."
        )
        state.user_context.ready_for_orchestrator = True
        state.ready_for_completion = True
        state.mark_step_completed(OnboardingStep.COMPLETION)
        state.add_conversation_turn(state.last_user_message or "", response)
        return state

    async def process_message(
        self, user_id: UUID, message: str, state: OnboardingState | None = None
    ) -> tuple[str, OnboardingState]:
        if state is None:
            state = OnboardingState(user_id=user_id)
        state.last_user_message = message

        state_dict = state.model_dump()
        result = await self.graph.ainvoke(
            state_dict,
            config={
                "callbacks": [langfuse_handler],
                "thread_id": str(state.conversation_id),
                "tags": ["onboarding", "verde-ai"],
                "configurable": {
                    "session_id": str(state.conversation_id),
                    "original_query": message,
                },
            },
        )
        new_state = OnboardingState(**result) if isinstance(result, dict) else result

        return (new_state.last_agent_response or "", new_state)

    async def process_message_with_events(
        self,
        user_id: UUID,
        message: str,
        state: OnboardingState | None,
        on_sse_event: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> OnboardingState:
        """Process a message and emit minimal SSE updates using ainvoke (no event streaming)."""
        if state is None:
            state = OnboardingState(user_id=user_id)
        state.last_user_message = message

        prev_completed = set(s.value for s in state.completed_steps)

        await on_sse_event(
            {
                "event": "step.update",
                "data": {"status": "validating", "step_id": state.current_step.value},
            }
        )

        result = await self.graph.ainvoke(
            state.model_dump(),
            config={
                "callbacks": [langfuse_handler],
                "thread_id": str(state.conversation_id),
                "tags": ["onboarding", "verde-ai"],
                "configurable": {
                    "session_id": str(state.conversation_id),
                    "original_query": message,
                },
            },
        )
        new_state = OnboardingState(**result) if isinstance(result, dict) else result

        new_completed = set(s.value for s in new_state.completed_steps)
        for step_value in sorted(new_completed - prev_completed):
            await on_sse_event(
                {
                    "event": "step.update",
                    "data": {"status": "completed", "step_id": step_value},
                }
            )

        final_text = new_state.last_agent_response or ""
        if final_text:
            await on_sse_event({"event": "token.delta", "data": {"text": final_text}})

        await on_sse_event(
            {
                "event": "step.update",
                "data": {
                    "status": "presented",
                    "step_id": new_state.current_step.value,
                },
            }
        )

        if (
            new_state.ready_for_completion
            and new_state.user_context.ready_for_orchestrator
        ):
            await on_sse_event(
                {"event": "onboarding.status", "data": {"status": "done"}}
            )

        return new_state
