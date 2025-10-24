import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from app.models import UserContext

from .types import Choice, FlowStep, InteractionType

logger = logging.getLogger(__name__)


class OnboardingState(BaseModel):
    conversation_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    current_flow_step: FlowStep = FlowStep.PRESENTATION
    turn_number: int = 0

    show_complete_welcome_message: bool = True

    user_context: UserContext = Field(default_factory=lambda: UserContext())

    conversation_history: list[dict[str, Any]] = Field(default_factory=list)

    last_user_message: str | None = None
    last_agent_response: str | None = None

    ready_for_completion: bool = False

    current_interaction_type: InteractionType = InteractionType.FREE_TEXT
    current_choices: list[Choice] = Field(default_factory=list)

    @model_validator(mode="after")
    def _sync_user_context_user_id(self) -> "OnboardingState":
        try:
            if (
                self.user_context is not None
                and self.user_id is not None
                and getattr(self.user_context, "user_id", None) != self.user_id
            ):
                self.user_context.user_id = self.user_id
        except Exception as e:
            logger.warning("[ONBOARDING] Failed to sync user_context.user_id: %s", e)
        return self

    def ensure_completion_consistency(self) -> None:
        if getattr(self.user_context, "ready_for_orchestrator", False):
            self.ready_for_completion = True

    def add_conversation_turn(self, user_message: str, agent_response: str) -> None:
        turn = {
            "turn_number": self.turn_number,
            "user_message": user_message,
            "agent_response": agent_response,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self.conversation_history.append(turn)
        if len(self.conversation_history) > 50:
            self.conversation_history = self.conversation_history[-50:]
        self.turn_number += 1
        self.last_user_message = user_message
        self.last_agent_response = agent_response

    def can_complete(self) -> bool:
        has_name = bool(self.user_context.preferred_name)
        return has_name and self.ready_for_completion
