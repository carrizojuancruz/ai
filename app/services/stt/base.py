"""Base STT service interface.

This module defines the abstract base class for all STT providers,
ensuring a consistent interface across different implementations.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, Optional

logger = logging.getLogger(__name__)


class STTService(ABC):
    """Abstract base class for Speech-to-Text services.

    All STT providers must implement this interface to ensure
    consistent behavior across the application.
    """

    def __init__(self, model: Optional[str] = None, sample_rate: int = 16000):
        """Initialize the STT service.

        Args:
            model: The model identifier for transcription
            sample_rate: Expected audio sample rate

        """
        self.model = model
        self.sample_rate = sample_rate
        self.logger = logger

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, mime_type: Optional[str] = None) -> Dict[str, Any]:
        """Transcribe full audio content and return a result dict with at least {"text": str}."""
        raise NotImplementedError

    @abstractmethod
    async def transcribe_stream(self, audio_stream: AsyncIterator[bytes], mime_type: Optional[str] = None) -> AsyncIterator[Dict[str, Any]]:
        """Streaming transcription; yields partial results/events."""
        raise NotImplementedError

    @abstractmethod
    async def validate_audio(self, audio_bytes: bytes, mime_type: Optional[str] = None) -> bool:
        """Validate audio payload for size/format constraints."""
        raise NotImplementedError

    @abstractmethod
    async def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current STT model/provider."""
        raise NotImplementedError

    def get_provider_name(self) -> str:
        return self.__class__.__name__.replace("STTService", "").lower()

    def get_config(self) -> Dict[str, Any]:
        return {
            "provider": self.get_provider_name(),
            "model": self.model,
            "sample_rate": self.sample_rate,
        }


class STTServiceError(Exception):
    """Exception raised when STT service operations fail."""

    def __init__(self, message: str, error_code: Optional[str] = None, provider: Optional[str] = None):
        super().__init__(message)
        self.error_code = error_code
        self.provider = provider
