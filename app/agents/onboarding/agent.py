"""LangGraph-based onboarding agent implementation."""

from uuid import UUID

from langgraph.graph import END, StateGraph

from app.models import MemoryCategory
from app.services.llm import get_llm_client
from .prompts import build_generation_prompt
from .state import OnboardingState, OnboardingStep


class OnboardingAgent:
    """Onboarding Agent for the Verde AI application."""

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

        fn, mp = route_for(OnboardingStep.KB_EDUCATION, "completion")
        workflow.add_conditional_edges("kb_education", fn, mp)

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
            name = self.llm.extract(
                schema={
                    "type": "object",
                    "properties": {"preferred_name": {"type": "string"}},
                    "required": ["preferred_name"],
                },
                text=state.last_user_message,
                instructions="Extract the user's preferred_name only.",
            ).get("preferred_name")
            if name and not self._is_probable_greeting(name):
                state.user_context.identity.preferred_name = name
                state.user_context.sync_nested_to_flat()
            else:
                response = self._gen(
                    OnboardingStep.GREETING, state, ["identity.preferred_name"]
                )
                state.add_conversation_turn(state.last_user_message or "", response)
                return state

        if state.user_context.identity.preferred_name:
            state.mark_step_completed(OnboardingStep.GREETING)
            response = self._gen(OnboardingStep.LANGUAGE_TONE, state, ["style.tone"])
        else:
            response = self._gen(OnboardingStep.GREETING, state, missing)
        state.add_conversation_turn(state.last_user_message or "", response)
        return state

    async def _handle_language_tone(self, state: OnboardingState) -> OnboardingState:
        state.current_step = OnboardingStep.LANGUAGE_TONE
        missing = []
        if not state.user_context.style.tone:
            missing.append("style.tone")
        if not state.user_context.safety.blocked_categories:
            missing.append("safety.blocked_categories")
        if state.user_context.safety.allow_sensitive is None:
            missing.append("safety.allow_sensitive")

        if state.last_user_message and not state.user_context.style.tone:
            data = self.llm.extract(
                schema={
                    "type": "object",
                    "properties": {
                        "tone": {"type": "string"},
                        "verbosity": {"type": "string"},
                        "formality": {"type": "string"},
                        "emojis": {"type": "string"},
                        "blocked_categories": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "allow_sensitive": {"type": "boolean"},
                    },
                    "required": ["tone"],
                },
                text=state.last_user_message,
                instructions="Extract style.{tone,verbosity,formality,emojis} and safety.{blocked_categories,allow_sensitive}.",
            )
            state.user_context.style.tone = (
                data.get("tone") or state.user_context.style.tone
            )
            state.user_context.style.verbosity = (
                data.get("verbosity") or state.user_context.style.verbosity
            )
            state.user_context.style.formality = (
                data.get("formality") or state.user_context.style.formality
            )
            state.user_context.style.emojis = (
                data.get("emojis") or state.user_context.style.emojis
            )
            if data.get("blocked_categories"):
                state.user_context.safety.blocked_categories = list(
                    data["blocked_categories"]
                )
            if data.get("allow_sensitive") is not None:
                state.user_context.safety.allow_sensitive = bool(
                    data["allow_sensitive"]
                )
            state.user_context.sync_nested_to_flat()

        if (
            state.user_context.style.tone
            and state.user_context.safety.blocked_categories
            and isinstance(state.user_context.safety.allow_sensitive, bool)
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
            mood = self.llm.extract(
                schema={"type": "object", "properties": {"mood": {"type": "string"}}},
                text=state.last_user_message,
                instructions="Extract a short mood phrase.",
            ).get("mood")
            if mood:
                state.add_semantic_memory(
                    content=f"User's current mood about money: {mood}",
                    category=MemoryCategory.PERSONAL,
                    metadata={"type": "mood", "value": mood, "context": "money"},
                )
        if any(
            m.get("metadata", {}).get("type") == "mood" for m in state.semantic_memories
        ):
            state.mark_step_completed(OnboardingStep.MOOD_CHECK)
            response = self._gen(OnboardingStep.PERSONAL_INFO, state, ["location.city"])
        else:
            response = self._gen(OnboardingStep.MOOD_CHECK, state, ["mood"])
        state.add_conversation_turn(state.last_user_message or "", response)
        return state

    async def _handle_personal_info(self, state: OnboardingState) -> OnboardingState:
        state.current_step = OnboardingStep.PERSONAL_INFO
        missing = []
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
        missing = []
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
                state.user_context.goals = list(data["goals"])
            if data.get("income"):
                state.user_context.income = data["income"]
            if data.get("primary_financial_goal"):
                state.user_context.primary_financial_goal = data[
                    "primary_financial_goal"
                ]
            state.user_context.sync_nested_to_flat()

        if state.user_context.goals and state.user_context.income:
            state.mark_step_completed(OnboardingStep.FINANCIAL_SNAPSHOT)
            response = self._gen(
                OnboardingStep.SOCIALS_OPTIN, state, ["proactivity.opt_in"]
            )
        else:
            response = self._gen(OnboardingStep.FINANCIAL_SNAPSHOT, state, missing)
        state.add_conversation_turn(state.last_user_message or "", response)
        return state

    async def _handle_socials_optin(self, state: OnboardingState) -> OnboardingState:
        state.current_step = OnboardingStep.SOCIALS_OPTIN
        if state.last_user_message:
            consent = self.llm.extract(
                schema={
                    "type": "object",
                    "properties": {"opt_in": {"type": "boolean"}},
                },
                text=state.last_user_message,
                instructions="Return opt_in as boolean when answer implies yes/no.",
            ).get("opt_in")
            state.user_context.social_signals_consent = (
                bool(consent) if consent is not None else False
            )
        if isinstance(state.user_context.social_signals_consent, bool):
            state.mark_step_completed(OnboardingStep.SOCIALS_OPTIN)
            response = self._gen(OnboardingStep.KB_EDUCATION, state, [])
        else:
            response = self._gen(
                OnboardingStep.SOCIALS_OPTIN, state, ["proactivity.opt_in"]
            )
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
        """Display the onboarding LangGraph as a PNG (for notebooks)."""
        try:
            from IPython.display import Image, display
            display(Image(self.graph.get_graph().draw_mermaid_png()))
        except Exception:
            pass
