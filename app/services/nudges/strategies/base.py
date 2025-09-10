from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from uuid import UUID

from app.services.nudges.evaluator import NudgeCandidate


class NudgeStrategy(ABC):
    """Abstract base class for nudge evaluation strategies."""

    @property
    @abstractmethod
    def nudge_type(self) -> str:
        pass

    @property
    @abstractmethod
    def requires_fos_text(self) -> bool:
        pass

    @abstractmethod
    async def evaluate(self, user_id: UUID, context: Dict[str, Any]) -> Optional[NudgeCandidate]:
        """Return NudgeCandidate if nudge should be sent, None otherwise."""
        pass

    @abstractmethod
    def get_priority(self, context: Dict[str, Any]) -> int:
        """Return priority score (1-5) for this nudge type."""
        pass

    async def validate_conditions(self, user_id: UUID) -> bool:
        """Validate common conditions (can be overridden)."""
        return True

    async def cleanup(self, user_id: UUID) -> None:
        """Perform cleanup after evaluation (optional override)."""
        pass
