"""Provider-agnostic LLM interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
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

    async def generate_stream(
        self,
        prompt: str,
        system: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        """Stream generated response tokens. Default implementation chunks the full response."""
        full_response = self.generate(prompt, system, context)
        chunk_size = 10
        for i in range(0, len(full_response), chunk_size):
            yield full_response[i : i + chunk_size]

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
