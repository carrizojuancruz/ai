"""LLM client factory and configuration."""

from __future__ import annotations

import logging
from typing import Final

from app.core.config import config

from .base import LLM
from .bedrock import BedrockLLM
from .stub import StubLLM

DEFAULT_PROVIDER: Final[str] = "stub"
logger = logging.getLogger(__name__)


def get_llm_client() -> LLM:
    provider = config.LLM_PROVIDER.strip().lower()
    logger.info(f"LLM provider requested: {provider}")
    try:
        if provider == "bedrock":
            logger.info("Initializing Bedrock provider")
            return BedrockLLM()
        logger.info("Initializing Stub provider")
        return StubLLM()
    except Exception as exc:
        logger.warning(
            f"Failed to initialize provider '{provider}': {exc}. Falling back to stub"
        )
        return StubLLM()
