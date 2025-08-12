"""Onboarding agent state management."""

from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.models import BlockedTopic, SemanticMemory, UserContext


class OnboardingStep(str, Enum):
    """Steps in the onboarding conversation flow (Epic 01 stories)."""

    GREETING = "greeting"                    # Story 1: Greeting & Name/Pronouns
    LANGUAGE_TONE = "language_tone"          # Story 2: Language, Tone & Blocked Topics
    MOOD_CHECK = "mood_check"                # Story 3: Mood Check (Initial)
    PERSONAL_INFO = "personal_info"          # Story 4: Manual Personal Info (Minimal)
    FINANCIAL_SNAPSHOT = "financial_snapshot"  # Story 5: Manual Financial Snapshot
    SOCIALS_OPTIN = "socials_optin"          # Story 6: Socials Opt-In (Optional)
    KB_EDUCATION = "kb_education"            # Story 7: KB Education Small Talk
    COMPLETION = "completion"                # Story 8: Handoff Summary & Completion


class OnboardingState(BaseModel):
    """State for the onboarding agent conversation."""

    conversation_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    current_step: OnboardingStep = OnboardingStep.GREETING
    turn_number: int = 0

    user_context: UserContext = Field(default_factory=lambda: UserContext())

    semantic_memories: list[SemanticMemory] = Field(default_factory=list)
    blocked_topics: list[BlockedTopic] = Field(default_factory=list)

    conversation_history: list[dict[str, Any]] = Field(default_factory=list)

    completed_steps: list[OnboardingStep] = Field(default_factory=list)
    skipped_steps: list[OnboardingStep] = Field(default_factory=list)

    last_user_message: str | None = None
    last_agent_response: str | None = None

    ready_for_completion: bool = False
    completion_summary: str | None = None

    def mark_step_completed(self, step: OnboardingStep) -> None:
        """Mark a step as completed."""
        if step not in self.completed_steps:
            self.completed_steps.append(step)

    def mark_step_skipped(self, step: OnboardingStep) -> None:
        """Mark a step as skipped."""
        if step not in self.skipped_steps:
            self.skipped_steps.append(step)

    def add_semantic_memory(
        self, content: str, category: str, metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a semantic memory entry."""
        memory = SemanticMemory(
            user_id=self.user_id,
            content=content,
            category=category,
            metadata=metadata or {},
            source="onboarding",
        )
        self.semantic_memories.append(memory)

    def add_blocked_topic(self, topic: str, reason: str | None = None) -> None:
        """Add a blocked topic."""
        blocked_topic = BlockedTopic(
            user_id=self.user_id,
            topic=topic,
            reason=reason,
        )
        self.blocked_topics.append(blocked_topic)

    def add_conversation_turn(self, user_message: str, agent_response: str) -> None:
        """Add a conversation turn to history."""
        self.turn_number += 1
        self.conversation_history.append({
            "turn": self.turn_number,
            "user_message": user_message,
            "agent_response": agent_response,
            "step": self.current_step.value,
            "timestamp": "utcnow",
        })
        self.last_user_message = user_message
        self.last_agent_response = agent_response

    def get_next_step(self) -> OnboardingStep | None:
        """Determine the next step in the onboarding flow."""
        step_order = [
            OnboardingStep.GREETING,
            OnboardingStep.LANGUAGE_TONE,
            OnboardingStep.MOOD_CHECK,
            OnboardingStep.PERSONAL_INFO,
            OnboardingStep.FINANCIAL_SNAPSHOT,
            OnboardingStep.SOCIALS_OPTIN,
            OnboardingStep.KB_EDUCATION,
            OnboardingStep.COMPLETION,
        ]

        current_index = step_order.index(self.current_step)

        if current_index >= len(step_order) - 1:
            return None

        return step_order[current_index + 1]

    def can_complete(self) -> bool:
        """Check if we have minimum required info to complete onboarding."""
        has_name = bool(self.user_context.preferred_name)
        has_language = bool(self.user_context.language)
        return has_name and has_language
