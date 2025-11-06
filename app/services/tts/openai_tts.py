"""OpenAI TTS service implementation.

This module provides TTS functionality using OpenAI's text-to-speech API.
"""

import logging
from typing import Any, Dict

import httpx

from app.core.config import config

from .base import TTSService, TTSServiceError

logger = logging.getLogger(__name__)


class OpenAITTSService(TTSService):
    """OpenAI TTS service implementation using OpenAI's speech API."""

    def __init__(self):
        """Initialize the OpenAI TTS service."""
        super().__init__(
            voice_id=config.OPENAI_TTS_VOICE,
            output_format=config.TTS_OUTPUT_FORMAT,
            engine=config.TTS_ENGINE
        )
        self.openai_client = None
        self._initialize_client()
        self.supported_voices = self._get_supported_voices()
        self.supported_output_formats = self._get_supported_output_formats()

    def _initialize_client(self) -> None:
        """Initialize the OpenAI TTS client."""
        try:
            if not config.OPENAI_API_KEY:
                raise TTSServiceError("OPENAI_API_KEY is required for OpenAI provider", provider="openai")

            self.openai_client = httpx.AsyncClient(timeout=30.0)
            self.logger.info(f"OpenAI TTS service initialized with voice_id={self.voice_id}")
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenAI TTS client: {e}")
            raise TTSServiceError(f"Failed to initialize OpenAI client: {e}", provider="openai") from e

    @staticmethod
    def _get_supported_voices() -> list[str]:
        """Get a list of supported voices for this provider."""
        return [
            "alloy", "ash", "ballad", "coral", "echo", "fable", "onyx", "nova", "sage", "shimmer", "verse"
        ]

    @staticmethod
    def _get_supported_output_formats() -> list[str]:
        """Get a list of supported output formats for this provider."""
        return ["mp3", "opus", "aac", "flac", "wav", "pcm"]


    async def synthesize_speech(self, text: str) -> bytes:
        """Convert text to speech using OpenAI API.

        Args:
            text: The text to convert to speech

        Returns:
            bytes: The generated audio data

        Raises:
            TTSServiceError: If synthesis fails

        """
        if not self.openai_client:
            raise TTSServiceError("OpenAI client not initialized", provider="openai")

        if not await self.validate_text(text):
            raise TTSServiceError("Invalid text for synthesis", provider="openai")

        try:
            self.logger.info(f"Synthesizing speech for text length: {len(text)} characters")

            # Call the async method directly
            audio_data = await self._synthesize_speech_async(text)

            self.logger.info(f"Successfully synthesized {len(audio_data)} bytes of audio")

            return audio_data

        except Exception as e:
            self.logger.error(f"TTS synthesis failed: {e}")
            raise TTSServiceError(f"Synthesis failed: {str(e)}", provider="openai") from e

    async def _synthesize_speech_async(self, text: str) -> bytes:
        """Make async OpenAI TTS API request.

        Args:
            text: The text to synthesize

        Returns:
            bytes: The generated audio data

        """
        response = await self.openai_client.post(
            "https://api.openai.com/v1/audio/speech",
            json={
                "model": config.OPENAI_TTS_MODEL,
                "input": text,
                "voice": self.voice_id,  # Use configured voice
                "response_format": self.output_format,  # Use configured format
            },
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.OPENAI_API_KEY}",
            },
        )
        response.raise_for_status()
        return response.content

    async def get_voice_info(self) -> Dict[str, Any]:
        """Get information about the current voice configuration.

        Returns:
            Dict containing voice information

        """
        return {
            "provider": "openai",
            "voice_id": self.voice_id,
            "output_format": self.output_format,
            "supported_formats": self.supported_output_formats,
            "max_text_length": 4096,  # OpenAI limit
            "supported_voices": self.supported_voices
        }

    async def validate_text(self, text: str) -> bool:
        """Validate if the text is suitable for synthesis.

        Args:
            text: The text to validate

        Returns:
            bool: True if text is valid, False otherwise

        """
        if not text or not text.strip():
            self.logger.warning("Empty text provided for synthesis")
            return False

        if len(text) > 4096:  # OpenAI character limit
            self.logger.warning(f"Text too long for synthesis: {len(text)} characters")
            return False

        # Check for problematic characters or patterns
        if any(char in text for char in ['<', '>', '&']):
            self.logger.warning("Text contains potentially problematic characters")
            return False

        return True

    def get_available_voices(self) -> list[str]:
        """Get list of available voices for this provider.

        Returns:
            List of available voice IDs

        """
        return self.supported_voices

    async def test_connection(self) -> bool:
        """Test the connection to the TTS service.

        Returns:
            bool: True if connection is successful, False otherwise

        """
        try:
            if not self.openai_client:
                return False

            # Try a simple synthesis to test connection
            test_text = "Test"
            await self.synthesize_speech(test_text)
            return True

        except Exception as e:
            self.logger.error(f"TTS connection test failed: {e}")
            return False
