from __future__ import annotations

import logging
from typing import Any, Optional

from app.services.llm.bedrock import BedrockLLM
from app.services.llm.prompt_loader import prompt_loader

logger = logging.getLogger(__name__)

_LOCATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "city": {"type": ["string", "null"]},
        "region": {"type": ["string", "null"]},
    },
}


class LocationNormalizer:
    """LLM-backed helper to normalize free-form location into city + region."""

    def __init__(self) -> None:
        self._llm: Optional[BedrockLLM] = None

    def _get_llm(self) -> BedrockLLM:
        if self._llm is None:
            self._llm = BedrockLLM()
        return self._llm

    def normalize(self, raw: str) -> tuple[str | None, str | None]:
        """Return normalized (city, region); fall back to (raw, None) on failure."""
        if not isinstance(raw, str) or not raw.strip():
            return None, None

        text = raw.strip()
        try:
            llm = self._get_llm()
            instructions = prompt_loader.load("onboarding_location_extraction")
            result = llm.extract(schema=_LOCATION_SCHEMA, text=text, instructions=instructions)
            city = (result.get("city") or text or "").strip()
            region = (result.get("region") or "").strip()
            logger.info("[LOCATION_NORMALIZER] Extracted city=%s region=%s from '%s'", city, region, raw)
            return (city or None), (region or None)
        except Exception as exc:
            logger.warning("[LOCATION_NORMALIZER] Failed to normalize location '%s': %s", raw, exc)
            return text, None


location_normalizer = LocationNormalizer()
