"""STT service factory for provider selection.

This module provides a factory pattern to create STT service instances
based on configuration, allowing easy switching between providers.
"""

import logging
from typing import Optional

from app.core.config import config

from .base import STTService, STTServiceError
from .bedrock_stt import BedrockSTTService
from .openai_stt import OpenAISTTService

logger = logging.getLogger(__name__)

# Global STT service instance (singleton pattern)
_stt_service: Optional[STTService] = None


def get_stt_service() -> Optional[STTService]:
    """Get the configured STT service instance.

    Returns:
        STTService instance or None if STT is disabled

    Raises:
        STTServiceError: If the configured provider is not supported

    """
    global _stt_service

    # Return None if STT is disabled
    if not getattr(config, "AUDIO_ENABLED", False):
        logger.debug("STT is disabled, returning None STT service")
        return None

    # Return a cached instance if available
    if _stt_service is not None:
        return _stt_service

    # Create a new instance based on configuration
    provider = config.STT_PROVIDER.lower() if config.STT_PROVIDER else 'openai'

    try:
        if provider == "bedrock":
            _stt_service = BedrockSTTService()
            logger.info(f"Initialized {provider} STT service")
        elif provider == "openai":
            _stt_service = OpenAISTTService()
            logger.info(f"Initialized {provider} STT service")
        else:
            raise STTServiceError(f"Unsupported STT provider: {provider}")

        return _stt_service

    except Exception as e:
        logger.error(f"Failed to initialize STT service with provider '{provider}': {e}")
        raise STTServiceError(f"Failed to initialize STT service: {e}") from e


def create_stt_service(provider: str) -> STTService:
    """Create an STT service instance for a specific provider.

    Args:
        provider: The STT provider name

    Returns:
        STTService instance

    Raises:
        STTServiceError: If the provider is not supported

    """
    p = provider.lower()

    if p == "bedrock":
        return BedrockSTTService()
    elif p == "openai":
        return OpenAISTTService()
    else:
        raise STTServiceError(f"Unsupported STT provider: {provider}")


def get_supported_providers() -> list[str]:
    """Get list of supported STT providers."""
    return ["bedrock", "openai"]


def reset_stt_service() -> None:
    """Reset the global STT service instance.

    This is useful for testing or when configuration changes.
    """
    global _stt_service
    _stt_service = None
    logger.info("STT service instance reset")


def is_stt_available() -> bool:
    """Check if STT service is available and properly configured."""
    if not getattr(config, "AUDIO_ENABLED", False):
        return False

    try:
        service = get_stt_service()
        return service is not None
    except Exception as e:
        logger.warning(f"STT service not available: {e}")
        return False


async def test_stt_service() -> bool:
    """Test the STT service connection and functionality."""
    try:
        service = get_stt_service()
        if service is None:
            return False

        info = await service.get_model_info()
        return bool(info)

    except Exception as e:
        logger.error(f"STT service test failed: {e}")
        return False
