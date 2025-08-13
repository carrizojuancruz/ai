"""Provider-agnostic LLM interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class LLM(ABC):
    """Abstract LLM interface.

    Providers should implement free-form generation and structured extraction.
    """

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> str:
        """Return a generated response string."""
        raise NotImplementedError

    @abstractmethod
    def extract(
        self,
        schema: dict[str, Any],
        text: str,
        instructions: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Return a dict matching the provided JSON schema as best-effort."""
        raise NotImplementedError
