from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.models import BlockedTopic, SemanticMemory, UserContext


class OnboardingStep(str, Enum):
    WARMUP = "warmup"
    IDENTITY = "identity"
    INCOME_MONEY = "income_money"
    ASSETS_EXPENSES = "assets_expenses"
    HOME = "home"
    FAMILY_UNIT = "family_unit"
    HEALTH_COVERAGE = "health_coverage"
    LEARNING_PATH = "learning_path"
    PLAID_INTEGRATION = "plaid_integration"
    CHECKOUT_EXIT = "checkout_exit"

class OnboardingState(BaseModel):
    conversation_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    current_step: OnboardingStep = OnboardingStep.WARMUP
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

    skip_count: int = 0
    skipped_nodes: list[str] = Field(default_factory=list)

    current_interaction_type: str = "free_text"
    current_choices: list[dict[str, Any]] = Field(default_factory=list)
    current_binary_choices: dict[str, Any] | None = None
    multi_min: int | None = None
    multi_max: int | None = None

    def mark_step_completed(self, step: OnboardingStep) -> None:
        if step not in self.completed_steps:
            self.completed_steps.append(step)

    def mark_step_skipped(self, step: OnboardingStep) -> None:
        if step not in self.skipped_steps:
            self.skipped_steps.append(step)

    def add_semantic_memory(
        self,
        content: str,
        category: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        memory = SemanticMemory(
            user_id=self.user_id,
            content=content,
            category=category,
            metadata=metadata or {},
            source="onboarding",
        )
        self.semantic_memories.append(memory)

    def add_blocked_topic(self, topic: str, reason: str | None = None) -> None:
        blocked_topic = BlockedTopic(
            user_id=self.user_id,
            topic=topic,
            reason=reason,
        )
        self.blocked_topics.append(blocked_topic)

    def add_conversation_turn(self, user_message: str, agent_response: str) -> None:
        turn = {
            "turn_number": self.turn_number,
            "user_message": user_message,
            "agent_response": agent_response,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self.conversation_history.append(turn)
        self.turn_number += 1
        self.last_user_message = user_message
        self.last_agent_response = agent_response

    def has_mentioned_topic(self, keywords: list[str]) -> bool:
        all_text = ""
        for turn in self.conversation_history:
            all_text += f" {turn.get('user_message', '')} {turn.get('agent_response', '')}"
        all_text = all_text.lower()
        return any(keyword.lower() in all_text for keyword in keywords)

    def should_show_conditional_node(self, node: OnboardingStep) -> bool:
        if node == OnboardingStep.HOME:
            keywords = [
                "house",
                "home",
                "housing",
                "rent",
                "mortgage",
                "apartment",
                "buy a house",
                "home buying",
                "real estate",
                "property",
                "living",
                "move",
                "relocate",
                "downsize",
                "upgrade home",
                "landlord",
                "lease",
                "down payment",
                "homeowner",
            ]
            return self.has_mentioned_topic(keywords)
        elif node == OnboardingStep.FAMILY_UNIT:
            keywords = [
                "family",
                "children",
                "kids",
                "child",
                "dependents",
                "spouse",
                "partner",
                "husband",
                "wife",
                "married",
                "parent",
                "parenting",
                "childcare",
                "education fund",
                "college savings",
                "family planning",
                "baby",
                "pregnancy",
                "school",
                "daycare",
                "family expenses",
            ]
            return self.has_mentioned_topic(keywords)
        elif node == OnboardingStep.HEALTH_COVERAGE:
            keywords = [
                "health",
                "medical",
                "doctor",
                "hospital",
                "medication",
                "insurance",
                "sick",
                "treatment",
                "therapy",
                "prescription",
                "medical bills",
                "healthcare",
                "clinic",
                "surgery",
            ]
            return self.has_mentioned_topic(keywords)
        return False

    def get_next_step(self) -> OnboardingStep | None:
        if self.skip_count >= 3:
            return OnboardingStep.PLAID_INTEGRATION
        if self.current_step == OnboardingStep.WARMUP:
            return OnboardingStep.IDENTITY
        elif self.current_step == OnboardingStep.IDENTITY:
            if self.last_user_message and "learn" in self.last_user_message.lower():
                return OnboardingStep.LEARNING_PATH
            return OnboardingStep.INCOME_MONEY
        elif self.current_step == OnboardingStep.INCOME_MONEY:
            income_range = self.user_context.income
            if income_range in ["75k_100k", "over_100k"]:
                return OnboardingStep.ASSETS_EXPENSES
            return self._get_next_conditional_node()
        elif self.current_step == OnboardingStep.ASSETS_EXPENSES:
            return self._get_next_conditional_node()
        elif self.current_step == OnboardingStep.HOME:
            if self.should_show_conditional_node(OnboardingStep.FAMILY_UNIT):
                return OnboardingStep.FAMILY_UNIT
            elif self.should_show_conditional_node(OnboardingStep.HEALTH_COVERAGE):
                return OnboardingStep.HEALTH_COVERAGE
            return OnboardingStep.PLAID_INTEGRATION
        elif self.current_step == OnboardingStep.FAMILY_UNIT:
            if self.should_show_conditional_node(OnboardingStep.HEALTH_COVERAGE):
                return OnboardingStep.HEALTH_COVERAGE
            return OnboardingStep.PLAID_INTEGRATION
        elif self.current_step == OnboardingStep.HEALTH_COVERAGE or self.current_step == OnboardingStep.LEARNING_PATH:
            return OnboardingStep.PLAID_INTEGRATION
        elif self.current_step == OnboardingStep.PLAID_INTEGRATION:
            return OnboardingStep.CHECKOUT_EXIT
        elif self.current_step == OnboardingStep.CHECKOUT_EXIT:
            return None
        return None

    def _get_next_conditional_node(self) -> OnboardingStep:
        if self.should_show_conditional_node(OnboardingStep.HOME):
            return OnboardingStep.HOME
        elif self.should_show_conditional_node(OnboardingStep.FAMILY_UNIT):
            return OnboardingStep.FAMILY_UNIT
        elif self.should_show_conditional_node(OnboardingStep.HEALTH_COVERAGE):
            return OnboardingStep.HEALTH_COVERAGE
        return OnboardingStep.PLAID_INTEGRATION

    def can_complete(self) -> bool:
        has_name = bool(self.user_context.preferred_name)
        has_language = bool(self.user_context.language)
        return has_name and has_language
