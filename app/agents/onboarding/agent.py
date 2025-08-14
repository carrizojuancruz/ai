"""LangGraph-based onboarding agent (node-per-step, prompts-driven).

Each node is responsible for collecting its target fields using
LLM prompts and structured extraction, and decides whether to
advance or keep asking within the same node.
"""

from __future__ import annotations

from uuid import UUID
from typing import Any

from langgraph.graph import END, StateGraph

from app.models import MemoryCategory
from app.services.llm import get_llm_client
from .prompts import build_generation_prompt
from .state import OnboardingState, OnboardingStep


class OnboardingAgent:
    """Onboarding Agent implementing node-per-step logic with LLM prompts."""

    def __init__(self) -> None:
        self.graph = self._create_graph()
        self.llm = get_llm_client()

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

        def route_for(step: OnboardingStep, next_node: str):
            def _route(state: OnboardingState) -> str:
                return "next" if step in state.completed_steps else "stay"

            mapping = {"stay": END, "next": next_node}
            return _route, mapping

        fn, mp = route_for(OnboardingStep.GREETING, "language_tone")
        workflow.add_conditional_edges("greeting", fn, mp)

        fn, mp = route_for(OnboardingStep.LANGUAGE_TONE, "mood_check")
        workflow.add_conditional_edges("language_tone", fn, mp)

        fn, mp = route_for(OnboardingStep.MOOD_CHECK, "personal_info")
        workflow.add_conditional_edges("mood_check", fn, mp)

        fn, mp = route_for(OnboardingStep.PERSONAL_INFO, "financial_snapshot")
        workflow.add_conditional_edges("personal_info", fn, mp)

        fn, mp = route_for(OnboardingStep.FINANCIAL_SNAPSHOT, "socials_optin")
        workflow.add_conditional_edges("financial_snapshot", fn, mp)

        fn, mp = route_for(OnboardingStep.SOCIALS_OPTIN, "kb_education")
        workflow.add_conditional_edges("socials_optin", fn, mp)

        fn, mp = route_for(OnboardingStep.KB_EDUCATION, "style_finalize")
        workflow.add_conditional_edges("kb_education", fn, mp)

        fn, mp = route_for(OnboardingStep.STYLE_FINALIZE, "completion")
        workflow.add_conditional_edges("style_finalize", fn, mp)

        def route_completion(state: OnboardingState) -> str:
            return (
                "next" if OnboardingStep.COMPLETION in state.completed_steps else "stay"
            )

        workflow.add_conditional_edges(
            "completion",
            route_completion,
            {"stay": END, "next": END},
        )

        workflow.set_entry_point("greeting")
        return workflow.compile()

    def _gen(
        self, step: OnboardingStep, state: OnboardingState, missing: list[str]
    ) -> str:
        system, prompt, ctx = build_generation_prompt(
            step=step, user_context=state.user_context, missing_fields=missing
        )
        return self.llm.generate(prompt=prompt, system=system, context=ctx)

    def _is_probable_greeting(self, text: str) -> bool:
        term = (text or "").strip().lower()
        return term in {
            "hi",
            "hello",
            "hey",
            "hola",
            "buenas",
            "good morning",
            "good afternoon",
            "good evening",
        }

    async def _handle_greeting(self, state: OnboardingState) -> OnboardingState:
        state.current_step = OnboardingStep.GREETING
        missing: list[str] = []
        if not state.user_context.identity.preferred_name:
            missing.append("identity.preferred_name")

        if state.last_user_message and not state.user_context.identity.preferred_name:
            data = self.llm.extract(
                schema={
                    "type": "object",
                    "properties": {"preferred_name": {"type": "string"}},
                    "required": [],
                },
                text=state.last_user_message,
                instructions="If the user provided a name, extract it as preferred_name; otherwise return nothing.",
            )
            name = (data.get("preferred_name") or "").strip()
            if name and not self._is_probable_greeting(name):
                state.user_context.identity.preferred_name = name
                state.user_context.sync_nested_to_flat()
                state.mark_step_completed(OnboardingStep.GREETING)
                response = self._gen(
                    OnboardingStep.LANGUAGE_TONE,
                    state,
                    ["safety.blocked_categories", "safety.allow_sensitive"],
                )
            else:
                response = self._gen(
                    OnboardingStep.GREETING, state, ["identity.preferred_name"]
                )
            state.add_conversation_turn(state.last_user_message or "", response)
            return state

        if state.user_context.identity.preferred_name:
            state.mark_step_completed(OnboardingStep.GREETING)
            response = self._gen(
                OnboardingStep.LANGUAGE_TONE,
                state,
                ["safety.blocked_categories", "safety.allow_sensitive"],
            )
        else:
            response = self._gen(OnboardingStep.GREETING, state, missing)
        state.add_conversation_turn(state.last_user_message or "", response)
        return state

    async def _handle_language_tone(self, state: OnboardingState) -> OnboardingState:
        state.current_step = OnboardingStep.LANGUAGE_TONE
        missing: list[str] = []
        # Only safety here; tone inference is done in STYLE_FINALIZE
        if state.user_context.safety.blocked_categories is None:
            state.user_context.safety.blocked_categories = []
        if not state.user_context.safety.blocked_categories:
            missing.append("safety.blocked_categories")
        if state.user_context.safety.allow_sensitive is None:
            missing.append("safety.allow_sensitive")

        if state.last_user_message:
            data = self.llm.extract(
                schema={
                    "type": "object",
                    "properties": {
                        "blocked_categories": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "allow_sensitive": {"type": "boolean"},
                    },
                    "required": [],
                },
                text=state.last_user_message,
                instructions=(
                    "Normalize safety preferences from the message. If the user indicates none/no blocked topics, "
                    "return an empty array for blocked_categories. Infer allow_sensitive from yes/no phrasing."
                ),
            )
            if data.get("blocked_categories") is not None:
                state.user_context.safety.blocked_categories = list(
                    data.get("blocked_categories") or []
                )
            if data.get("allow_sensitive") is not None:
                state.user_context.safety.allow_sensitive = bool(
                    data["allow_sensitive"]
                )
        state.user_context.sync_nested_to_flat()

        if state.user_context.safety.blocked_categories is not None and isinstance(
            state.user_context.safety.allow_sensitive, bool
        ):
            state.mark_step_completed(OnboardingStep.LANGUAGE_TONE)
            response = self._gen(OnboardingStep.MOOD_CHECK, state, ["mood"])
        else:
            response = self._gen(OnboardingStep.LANGUAGE_TONE, state, missing)
        state.add_conversation_turn(state.last_user_message or "", response)
        return state

    async def _handle_mood_check(self, state: OnboardingState) -> OnboardingState:
        state.current_step = OnboardingStep.MOOD_CHECK
        if state.last_user_message:
            data = self.llm.extract(
                schema={"type": "object", "properties": {"mood": {"type": "string"}}},
                text=state.last_user_message,
                instructions="Extract a short mood phrase.",
            )
            mood = data.get("mood")
            if mood:
                state.add_semantic_memory(
                    content=f"User's current mood about money: {mood}",
                    category=MemoryCategory.PERSONAL,
                    metadata={"type": "mood", "value": mood, "context": "money"},
                )
        if any(
            getattr(m, "metadata", {}).get("type") == "mood"
            for m in state.semantic_memories
        ):
            state.mark_step_completed(OnboardingStep.MOOD_CHECK)
            response = self._gen(OnboardingStep.PERSONAL_INFO, state, ["location.city"])
        else:
            response = self._gen(OnboardingStep.MOOD_CHECK, state, ["mood"])
        state.add_conversation_turn(state.last_user_message or "", response)
        return state

    async def _handle_personal_info(self, state: OnboardingState) -> OnboardingState:
        state.current_step = OnboardingStep.PERSONAL_INFO
        missing: list[str] = []
        if not state.user_context.location.city:
            missing.append("location.city")
        if not state.user_context.location.region:
            missing.append("location.region")
        if state.last_user_message:
            data = self.llm.extract(
                schema={
                    "type": "object",
                    "properties": {
                        "city": {"type": "string"},
                        "region": {"type": "string"},
                    },
                },
                text=state.last_user_message,
                instructions="Extract location.city and location.region when present.",
            )
            if data.get("city"):
                state.user_context.location.city = data["city"]
            if data.get("region"):
                state.user_context.location.region = data["region"]
            state.user_context.sync_nested_to_flat()

        if state.user_context.location.city and state.user_context.location.region:
            state.mark_step_completed(OnboardingStep.PERSONAL_INFO)
            response = self._gen(OnboardingStep.FINANCIAL_SNAPSHOT, state, ["goals"])
        else:
            response = self._gen(OnboardingStep.PERSONAL_INFO, state, missing)
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
        if state.last_user_message:
            data = self.llm.extract(
                schema={
                    "type": "object",
                    "properties": {
                        "goals": {"type": "array", "items": {"type": "string"}},
                        "income": {"type": "string"},
                        "primary_financial_goal": {"type": "string"},
                    },
                },
                text=state.last_user_message,
                instructions="Extract goals (array of short strings), income band, and primary_financial_goal if present.",
            )
            if data.get("goals"):
                state.user_context.goals = (
                    list(data["goals"]) or state.user_context.goals
                )
            if data.get("income"):
                state.user_context.income = data["income"]
            if data.get("primary_financial_goal"):
                state.user_context.primary_financial_goal = data[
                    "primary_financial_goal"
                ]
            state.user_context.sync_nested_to_flat()

        if state.user_context.goals and state.user_context.income:
            state.mark_step_completed(OnboardingStep.FINANCIAL_SNAPSHOT)
            response = self._gen(OnboardingStep.SOCIALS_OPTIN, state, [])
        else:
            response = self._gen(OnboardingStep.FINANCIAL_SNAPSHOT, state, missing)
        state.add_conversation_turn(state.last_user_message or "", response)
        return state

    async def _handle_socials_optin(self, state: OnboardingState) -> OnboardingState:
        state.current_step = OnboardingStep.SOCIALS_OPTIN
        if state.last_user_message:
            data = self.llm.extract(
                schema={
                    "type": "object",
                    "properties": {"opt_in": {"type": "boolean"}},
                },
                text=state.last_user_message,
                instructions="Return opt_in as boolean when answer implies yes/no.",
            )
            opt_in = data.get("opt_in")
            if opt_in is not None:
                state.user_context.social_signals_consent = bool(opt_in)

        if isinstance(state.user_context.social_signals_consent, bool):
            state.mark_step_completed(OnboardingStep.SOCIALS_OPTIN)
            response = self._gen(OnboardingStep.KB_EDUCATION, state, [])
        else:
            response = self._gen(OnboardingStep.SOCIALS_OPTIN, state, [])
        state.add_conversation_turn(state.last_user_message or "", response)
        return state

    async def _handle_kb_education(self, state: OnboardingState) -> OnboardingState:
        state.current_step = OnboardingStep.KB_EDUCATION
        if state.last_user_message:
            state.mark_step_completed(OnboardingStep.KB_EDUCATION)
            response = self._gen(OnboardingStep.COMPLETION, state, [])
        else:
            response = self._gen(OnboardingStep.KB_EDUCATION, state, [])
        state.add_conversation_turn(state.last_user_message or "", response)
        return state

    async def _handle_style_finalize(self, state: OnboardingState) -> OnboardingState:
        state.current_step = OnboardingStep.STYLE_FINALIZE
        missing: list[str] = []
        if not state.user_context.style.tone:
            missing.append("style.tone")
        if not state.user_context.style.verbosity:
            missing.append("style.verbosity")
        if not state.user_context.style.formality:
            missing.append("style.formality")
        if not state.user_context.style.emojis:
            missing.append("style.emojis")
        if not state.user_context.accessibility.reading_level_hint:
            missing.append("accessibility.reading_level_hint")
        if not state.user_context.accessibility.glossary_level_hint:
            missing.append("accessibility.glossary_level_hint")

        last_turns_text = "\n".join(
            f"U:{t.get('user_message', '')}\nA:{t.get('agent_response', '')}"
            for t in state.conversation_history[-6:]
        )
        data = self.llm.extract(
            schema={
                "type": "object",
                "properties": {
                    "tone": {"type": "string"},
                    "verbosity": {"type": "string"},
                    "formality": {"type": "string"},
                    "emojis": {"type": "string"},
                    "reading_level_hint": {"type": "string"},
                    "glossary_level_hint": {"type": "string"},
                },
            },
            text=last_turns_text,
            instructions=(
                "Infer concise style.{tone,verbosity,formality,emojis} and accessibility.{reading_level_hint,glossary_level_hint} "
                "from the user's language and the assistant tone so far."
            ),
        )
        ctx = state.user_context
        if data.get("tone") and not ctx.style.tone:
            ctx.style.tone = data["tone"]
        if data.get("verbosity") and not ctx.style.verbosity:
            ctx.style.verbosity = data["verbosity"]
        if data.get("formality") and not ctx.style.formality:
            ctx.style.formality = data["formality"]
        if data.get("emojis") and not ctx.style.emojis:
            ctx.style.emojis = data["emojis"]
        if data.get("reading_level_hint") and not ctx.accessibility.reading_level_hint:
            ctx.accessibility.reading_level_hint = data["reading_level_hint"]
        if (
            data.get("glossary_level_hint")
            and not ctx.accessibility.glossary_level_hint
        ):
            ctx.accessibility.glossary_level_hint = data["glossary_level_hint"]
        ctx.sync_nested_to_flat()

        response = (
            "Before we wrap, I'll keep replies "
            f"{ctx.style.tone or 'clear'} and {ctx.style.formality or 'friendly'}. "
            "Sound good?"
        )
        state.add_conversation_turn(state.last_user_message or "", response)
        state.mark_step_completed(OnboardingStep.STYLE_FINALIZE)
        return state

    async def _handle_completion(self, state: OnboardingState) -> OnboardingState:
        state.current_step = OnboardingStep.COMPLETION
        response = self._gen(OnboardingStep.COMPLETION, state, [])
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
        result = await self.graph.ainvoke(state_dict)
        new_state = OnboardingState(**result) if isinstance(result, dict) else result

        return (new_state.last_agent_response or "", new_state)

    def display_graph(self) -> None:
        try:
            from IPython.display import Image, display

            display(Image(self.graph.get_graph().draw_mermaid_png()))
        except Exception:
            pass
