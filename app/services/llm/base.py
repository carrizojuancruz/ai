"""Provider-agnostic LLM interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLM(ABC):
    """Abstract LLM interface.

    Providers should implement free-form generation and structured extraction.
    """

    def set_callbacks(self, callbacks: list[Any] | None) -> None:
        """Optionally accept LangChain-style callbacks (no-op by default)."""
        return

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Return a generated response string."""
        raise NotImplementedError

    @abstractmethod
    def extract(
        self,
        schema: dict[str, Any],
        text: str,
        instructions: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return a dict matching the provided JSON schema as best-effort."""
        raise NotImplementedError
