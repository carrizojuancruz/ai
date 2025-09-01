from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from .models import ExternalSource


class ExternalSourcesRepositoryInterface(ABC):
    """Interface for external sources repository."""

    @abstractmethod
    async def get_all(self) -> List[ExternalSource]:
        """Get all sources from external API."""
        pass
