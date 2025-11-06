"""TTS service factory for provider selection.

This module provides a factory pattern to create TTS service instances
based on configuration, allowing easy switching between providers.
"""

import logging
from typing import Optional

from app.core.config import config

from .base import TTSService, TTSServiceError
from .bedrock_tts import BedrockTTSService
from .openai_tts import OpenAITTSService

logger = logging.getLogger(__name__)

# Global TTS service instance (singleton pattern)
_tts_service: Optional[TTSService] = None


def get_tts_service() -> Optional[TTSService]:
    """Get the configured TTS service instance.

    Returns:
        TTSService instance or None if audio is disabled

    Raises:
        TTSServiceError: If the configured provider is not supported

    """
    global _tts_service

    # Return None if audio is disabled
    if not config.AUDIO_ENABLED:
        logger.debug("Audio is disabled, returning None TTS service")
        return None

    # Return cached instance if available
    if _tts_service is not None:
        return _tts_service

    # Create new instance based on configuration
    provider = config.TTS_PROVIDER.lower() if config.TTS_PROVIDER else None

    try:
        if provider == "bedrock":
            # Hardcoded service use for now
            _tts_service = OpenAITTSService()
            #_tts_service = BedrockTTSService()
            logger.info(f"Initialized {provider} TTS service")
        elif provider == "openai":
            _tts_service = OpenAITTSService()
            logger.info(f"Initialized {provider} TTS service")
        else:
            raise TTSServiceError(f"Unsupported TTS provider: {provider}")

        return _tts_service

    except Exception as e:
        logger.error(f"Failed to initialize TTS service with provider '{provider}': {e}")
        raise TTSServiceError(f"Failed to initialize TTS service: {e}") from e


def create_tts_service(provider: str) -> TTSService:
    """Create a TTS service instance for a specific provider.

    Args:
        provider: The TTS provider name

    Returns:
        TTSService instance

    Raises:
        TTSServiceError: If the provider is not supported

    """
    provider = provider.lower()

    if provider == "bedrock":
        return BedrockTTSService()
    elif provider == "openai":
        return OpenAITTSService()
    else:
        raise TTSServiceError(f"Unsupported TTS provider: {provider}")


def get_supported_providers() -> list[str]:
    """Get list of supported TTS providers.

    Returns:
        List of supported provider names

    """
    return ["bedrock", "openai"]


def reset_tts_service() -> None:
    """Reset the global TTS service instance.

    This is useful for testing or when configuration changes.
    """
    global _tts_service
    _tts_service = None
    logger.info("TTS service instance reset")


def is_tts_available() -> bool:
    """Check if TTS service is available and properly configured.

    Returns:
        bool: True if TTS is available, False otherwise

    """
    if not config.AUDIO_ENABLED:
        return False

    try:
        service = get_tts_service()
        return service is not None
    except Exception as e:
        logger.warning(f"TTS service not available: {e}")
        return False


async def test_tts_service() -> bool:
    """Test the TTS service connection and functionality.

    Returns:
        bool: True if test passes, False otherwise

    """
    try:
        service = get_tts_service()
        if service is None:
            return False

        return await service.test_connection()

    except Exception as e:
        logger.error(f"TTS service test failed: {e}")
        return False
