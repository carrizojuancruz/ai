"""Base TTS service interface.

This module defines the abstract base class for all TTS providers,
ensuring a consistent interface across different implementations.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class TTSService(ABC):
    """Abstract base class for Text-to-Speech services.

    All TTS providers must implement this interface to ensure
    consistent behavior across the application.
    """

    def __init__(self, voice_id: str, output_format: str, engine: str = "neural"):
        """Initialize the TTS service.

        Args:
            voice_id: The voice identifier to use for synthesis
            output_format: The audio format (e.g., 'mp3', 'wav')
            engine: The TTS engine to use (e.g., 'neural', 'standard')

        """
        self.voice_id = voice_id
        self.output_format = output_format
        self.engine = engine
        self.logger = logger

    @abstractmethod
    async def synthesize_speech(self, text: str) -> bytes:
        """Convert text to speech and return audio data.

        Args:
            text: The text to convert to speech

        Returns:
            bytes: The generated audio data

        Raises:
            TTSServiceError: If synthesis fails

        """
        raise NotImplementedError

    @abstractmethod
    async def get_voice_info(self) -> Dict[str, Any]:
        """Get information about the current voice configuration.

        Returns:
            Dict containing voice information

        """
        raise NotImplementedError

    @abstractmethod
    async def validate_text(self, text: str) -> bool:
        """Validate if the text is suitable for synthesis.

        Args:
            text: The text to validate

        Returns:
            bool: True if text is valid, False otherwise

        """
        raise NotImplementedError

    def get_provider_name(self) -> str:
        """Get the name of the TTS provider.

        Returns:
            str: The provider name

        """
        return self.__class__.__name__.replace("TTSService", "").lower()

    def get_config(self) -> Dict[str, Any]:
        """Get the current TTS configuration.

        Returns:
            Dict containing the current configuration

        """
        return {
            "provider": self.get_provider_name(),
            "voice_id": self.voice_id,
            "output_format": self.output_format,
            "engine": self.engine
        }


class TTSServiceError(Exception):
    """Exception raised when TTS service operations fail."""

    def __init__(self, message: str, error_code: Optional[str] = None, provider: Optional[str] = None):
        """Initialize the TTS service error.

        Args:
            message: Human-readable error message
            error_code: Optional error code for programmatic handling
            provider: Optional provider name that caused the error

        """
        super().__init__(message)
        self.error_code = error_code
        self.provider = provider
