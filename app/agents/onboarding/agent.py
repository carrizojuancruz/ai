"""LangGraph-based onboarding agent implementation."""

from uuid import UUID

from langgraph.graph import END, StateGraph

from app.models import MemoryCategory

from .state import OnboardingState, OnboardingStep


class OnboardingAgent:
    """Onboarding agent that follows Epic 01 specification.

    Implements the 8-story conversation flow:
    1. Greeting & Name/Pronouns
    2. Language, Tone & Blocked Topics
    3. Mood Check (Initial)
    4. Manual Personal Info (Minimal)
    5. Manual Financial Snapshot (Optional)
    6. Socials Opt-In (Optional)
    7. KB Education Small Talk (Static RAG)
    8. Handoff Summary & Completion Token
    """

    def __init__(self) -> None:
        """Initialize the onboarding agent graph."""
        self.graph = self._create_graph()

    def _create_graph(self) -> StateGraph:
        """Create the LangGraph workflow for onboarding."""
        workflow = StateGraph(OnboardingState)

        workflow.add_node("greeting", self._handle_greeting)
        workflow.add_node("language_tone", self._handle_language_tone)
        workflow.add_node("mood_check", self._handle_mood_check)
        workflow.add_node("personal_info", self._handle_personal_info)
        workflow.add_node("financial_snapshot", self._handle_financial_snapshot)
        workflow.add_node("socials_optin", self._handle_socials_optin)
        workflow.add_node("kb_education", self._handle_kb_education)
        workflow.add_node("completion", self._handle_completion)

        workflow.add_conditional_edges(
            "greeting",
            self._route_next_step,
            {
                "language_tone": "language_tone",
                "completion": "completion",
                "end": END,
            },
        )

        workflow.add_conditional_edges(
            "language_tone",
            self._route_next_step,
            {
                "mood_check": "mood_check",
                "completion": "completion",
                "end": END,
            },
        )

        workflow.add_conditional_edges(
            "mood_check",
            self._route_next_step,
            {
                "personal_info": "personal_info",
                "completion": "completion",
                "end": END,
            },
        )

        workflow.add_conditional_edges(
            "personal_info",
            self._route_next_step,
            {
                "financial_snapshot": "financial_snapshot",
                "completion": "completion",
                "end": END,
            },
        )

        workflow.add_conditional_edges(
            "financial_snapshot",
            self._route_next_step,
            {
                "socials_optin": "socials_optin",
                "completion": "completion",
                "end": END,
            },
        )

        workflow.add_conditional_edges(
            "socials_optin",
            self._route_next_step,
            {
                "kb_education": "kb_education",
                "completion": "completion",
                "end": END,
            },
        )

        workflow.add_conditional_edges(
            "kb_education",
            self._route_next_step,
            {
                "completion": "completion",
                "end": END,
            },
        )

        workflow.add_edge("completion", END)

        workflow.set_entry_point("greeting")

        return workflow.compile()

    def _route_next_step(self, state: OnboardingState) -> str:
        """Route to the next step or completion."""
        if state.ready_for_completion or state.can_complete():
            return "completion"

        next_step = state.get_next_step()
        if next_step is None:
            return "end"

        return next_step.value

    async def _handle_greeting(self, state: OnboardingState) -> OnboardingState:
        """Story 1: Greeting & Name/Pronouns."""
        state.current_step = OnboardingStep.GREETING

        if state.turn_number == 0:
            response = (
                "Hello! I'm Vera, your AI financial coach. I'm here to help you "
                "take control of your finances and reach your goals. 🌟\n\n"
                "To get started, I'd love to know what you'd like me to call you. "
                "What's your preferred name?"
            )
        else:
            user_message = state.last_user_message or ""

            name = user_message.strip()
            state.user_context.preferred_name = name

            response = (
                f"Nice to meet you, {name}! What pronouns would you like me to use "
                f"when referring to you? (e.g., she/her, he/him, they/them)"
            )

            state.add_semantic_memory(
                content=f"User's preferred name is {name}",
                category=MemoryCategory.PERSONAL,
                metadata={"type": "name", "value": name},
            )

        if (state.user_context.preferred_name
            and "pronouns" in (state.last_user_message or "").lower()):
                pronouns = state.last_user_message.strip()
                state.user_context.pronouns = pronouns

                state.add_semantic_memory(
                    content=f"User's pronouns are {pronouns}",
                    category=MemoryCategory.PERSONAL,
                    metadata={"type": "pronouns", "value": pronouns},
                )

                state.mark_step_completed(OnboardingStep.GREETING)
                response = (
                    f"Perfect! I'll use {pronouns} pronouns for you, "
                    f"{state.user_context.preferred_name}. Let's continue!"
                )

        state.add_conversation_turn(state.last_user_message or "", response)
        return state

    async def _handle_language_tone(self, state: OnboardingState) -> OnboardingState:
        """Story 2: Language, Tone & Blocked Topics Setup."""
        state.current_step = OnboardingStep.LANGUAGE_TONE

        response = (
            "I want to make sure I communicate with you in a way that feels right. "
            "Do you prefer more concise, direct responses, or would you like me to be "
            "more warm and conversational? Also, are there any financial topics you'd "
            "prefer not to discuss?"
        )

        if state.last_user_message:
            message = state.last_user_message.lower()

            if "concise" in message or "direct" in message:
                state.user_context.tone_preference = "concise"
            elif "warm" in message or "conversational" in message:
                state.user_context.tone_preference = "warm"

            if ("don't want" in message or "avoid" in message
                or "not discuss" in message):
                blocked_topic = message.replace("don't want to discuss", "").strip()
                if blocked_topic:
                    state.add_blocked_topic(blocked_topic, "User preference")

            state.add_semantic_memory(
                content=(
                    f"User prefers {state.user_context.tone_preference or 'neutral'} "
                    "communication tone"
                ),
                category=MemoryCategory.PERSONAL,
                metadata={
                    "type": "communication_style",
                    "value": state.user_context.tone_preference,
                },
            )

            state.mark_step_completed(OnboardingStep.LANGUAGE_TONE)
            response = "Got it! I'll adapt my communication style accordingly."

        state.add_conversation_turn(state.last_user_message or "", response)
        return state

    async def _handle_mood_check(self, state: OnboardingState) -> OnboardingState:
        """Story 3: Mood Check (Initial)."""
        state.current_step = OnboardingStep.MOOD_CHECK

        response = (
            f"Thanks for sharing that with me, {state.user_context.preferred_name}! "
            "Before we dive into your finances, I'm curious - how are you feeling "
            "about money today? Are you excited, stressed, curious, or something else?"
        )

        if state.last_user_message:
            mood = state.last_user_message.strip()

            state.add_semantic_memory(
                content=f"User's current mood about money: {mood}",
                category=MemoryCategory.PERSONAL,
                metadata={"type": "mood", "value": mood, "context": "money"},
            )

            state.mark_step_completed(OnboardingStep.MOOD_CHECK)
            response = (
                f"I appreciate you sharing that with me. I'll keep your {mood} "
                "feelings in mind as we work together."
            )

        state.add_conversation_turn(state.last_user_message or "", response)
        return state

    async def _handle_personal_info(self, state: OnboardingState) -> OnboardingState:
        """Story 4: Manual Personal Info (Minimal)."""
        state.current_step = OnboardingStep.PERSONAL_INFO

        response = (
            "Now I'd like to learn a bit about your situation to give you more "
            "personalized advice. This is totally optional! Would you like to share "
            "what city you're in, or if you have any dependents like children or "
            "family members you support financially?"
        )

        if state.last_user_message:
            message = state.last_user_message.lower()

            if "city" in message or "live in" in message:
                words = state.last_user_message.split()
                for i, word in enumerate(words):
                    if word.lower() in ["in", "city"] and i + 1 < len(words):
                            state.user_context.city = words[i + 1]

            if "children" in message or "dependents" in message:
                import re
                numbers = re.findall(r"\d+", state.last_user_message)
                if numbers:
                    state.user_context.dependents = int(numbers[0])

            state.mark_step_completed(OnboardingStep.PERSONAL_INFO)
            response = (
                "Thanks for sharing! This helps me understand your situation better."
            )

        state.add_conversation_turn(state.last_user_message or "", response)
        return state

    async def _handle_financial_snapshot(
        self, state: OnboardingState,
    ) -> OnboardingState:
        """Story 5: Manual Financial Snapshot (Optional)."""
        state.current_step = OnboardingStep.FINANCIAL_SNAPSHOT

        response = (
            "If you're comfortable sharing, it would help to know a bit about your "
            "financial situation. What's your main financial goal right now? And "
            "roughly what income range are you in? (This is completely optional "
            "and helps me give better advice)"
        )

        if state.last_user_message:
            message = state.last_user_message.lower()

            if "goal" in message or "want to" in message:
                goal = state.last_user_message.strip()
                state.user_context.primary_financial_goal = goal

                state.add_semantic_memory(
                    content=f"User's primary financial goal: {goal}",
                    category=MemoryCategory.GOALS,
                    metadata={"type": "primary_goal", "value": goal},
                )

            if "k" in message or "$" in message:
                state.user_context.income_band = "provided"

            state.mark_step_completed(OnboardingStep.FINANCIAL_SNAPSHOT)
            response = (
                "Thank you for sharing! This gives me a great foundation to help you."
            )

        state.add_conversation_turn(state.last_user_message or "", response)
        return state

    async def _handle_socials_optin(self, state: OnboardingState) -> OnboardingState:
        """Story 6: Socials Opt-In (Optional)."""
        state.current_step = OnboardingStep.SOCIALS_OPTIN

        response = (
            "One last optional thing - in the future, would you be interested in "
            "connecting social or behavioral signals to get even more personalized "
            "insights? You can always say no, and this won't affect your experience!"
        )

        if state.last_user_message:
            message = state.last_user_message.lower()

            if "yes" in message or "sure" in message or "okay" in message:
                state.user_context.social_signals_consent = True
            else:
                state.user_context.social_signals_consent = False

            state.mark_step_completed(OnboardingStep.SOCIALS_OPTIN)
            response = "Perfect! I've noted your preference."

        state.add_conversation_turn(state.last_user_message or "", response)
        return state

    async def _handle_kb_education(self, state: OnboardingState) -> OnboardingState:
        """Story 7: KB Education Small Talk (Static RAG)."""
        state.current_step = OnboardingStep.KB_EDUCATION

        response = (
            "Great! We're almost done with setup. Do you have any quick questions "
            "about personal finance that I can help answer while we finish up? "
            "(I can explain budgeting basics, saving strategies, or other "
            "financial concepts)"
        )

        if state.last_user_message:
            response = (
                "That's a great question! [KB Response would go here]. "
                "I'll remember that you're interested in this topic for our "
                "future conversations."
            )

            state.mark_step_completed(OnboardingStep.KB_EDUCATION)

        state.add_conversation_turn(state.last_user_message or "", response)
        return state

    async def _handle_completion(self, state: OnboardingState) -> OnboardingState:
        """Story 8: Handoff Summary & Completion Token."""
        state.current_step = OnboardingStep.COMPLETION

        name = state.user_context.preferred_name or "there"
        summary_parts = []

        if state.user_context.preferred_name:
            summary_parts.append(f"Your name is {state.user_context.preferred_name}")
        if state.user_context.tone_preference:
            summary_parts.append(
                f"you prefer {state.user_context.tone_preference} communication",
            )
        if state.user_context.primary_financial_goal:
            summary_parts.append(
                f"your main goal is {state.user_context.primary_financial_goal}",
            )

        summary = ", ".join(summary_parts) if summary_parts else "the basics about you"

        response = (
            f"Perfect, {name}! I've learned {summary}. "
            f"I'm ready to be your financial coach and help you reach your goals! "
            f"You can now ask me anything about budgeting, saving, investing, or "
            f"get personalized advice based on what you've shared. What would you "
            f"like to start with?"
        )

        state.user_context.ready_for_orchestrator = True
        state.ready_for_completion = True
        state.completion_summary = (
            f"Onboarding completed for {name}. Collected: {summary}."
        )
        state.mark_step_completed(OnboardingStep.COMPLETION)

        state.add_conversation_turn(state.last_user_message or "", response)
        return state

    async def process_message(
        self, user_id: UUID, message: str, state: OnboardingState | None = None,
    ) -> tuple[str, OnboardingState]:
        """Process a user message through the onboarding flow."""
        if state is None:
            state = OnboardingState(user_id=user_id)

        state.last_user_message = message

        result = await self.graph.ainvoke(state)

        return result.last_agent_response or "", result
