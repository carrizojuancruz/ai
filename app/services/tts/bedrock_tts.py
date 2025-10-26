"""AWS Bedrock TTS service implementation.

This module provides TTS functionality using AWS Bedrock/Polly service.
"""

import asyncio
import logging
from typing import Any, Dict

import boto3

from app.core.config import config

from .base import TTSService, TTSServiceError

logger = logging.getLogger(__name__)


class BedrockTTSService(TTSService):
    """AWS Bedrock TTS service implementation using Polly."""

    def __init__(self):
        """Initialize the Bedrock TTS service."""
        super().__init__(
            voice_id=config.TTS_VOICE_ID,
            output_format=config.TTS_OUTPUT_FORMAT,
            engine=config.TTS_ENGINE
        )
        self.polly_client = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize the AWS Polly client."""
        try:
            region = config.get_aws_region()
            if not region:
                raise TTSServiceError("AWS_REGION is required for Polly provider", provider="bedrock")

            self.polly_client = boto3.client('polly', region_name=region)
            self.logger.info(f"Polly TTS service initialized with voice_id={self.voice_id}")
        except Exception as e:
            self.logger.error(f"Failed to initialize Polly TTS client: {e}")
            raise TTSServiceError(f"Failed to initialize Polly client: {e}", provider="bedrock") from e

    async def synthesize_speech(self, text: str) -> bytes:
        """Convert text to speech using AWS Bedrock/Polly.

        Args:
            text: The text to convert to speech

        Returns:
            bytes: The generated audio data

        Raises:
            TTSServiceError: If synthesis fails

        """
        if not self.polly_client:
            raise TTSServiceError("Polly client not initialized", provider="bedrock")

        if not await self.validate_text(text):
            raise TTSServiceError("Invalid text for synthesis", provider="bedrock")

        try:
            self.logger.info(f"Synthesizing speech for text length: {len(text)} characters")

            # Run the synchronous Polly call in a thread pool
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                self._synthesize_speech_sync,
                text
            )

            audio_data = response['AudioStream'].read()
            self.logger.info(f"Successfully synthesized {len(audio_data)} bytes of audio")

            return audio_data

        except Exception as e:
            self.logger.error(f"TTS synthesis failed: {e}")
            raise TTSServiceError(f"Synthesis failed: {str(e)}", provider="bedrock") from e

    def _synthesize_speech_sync(self, text: str) -> Dict[str, Any]:
        """Wrap Polly synthesis synchronously.

        Args:
            text: The text to synthesize

        Returns:
            Dict containing the Polly response

        """
        return self.polly_client.synthesize_speech(
            VoiceId=self.voice_id,
            OutputFormat=self.output_format,
            Text=text,
            Engine=self.engine
        )

    async def get_voice_info(self) -> Dict[str, Any]:
        """Get information about the current voice configuration.

        Returns:
            Dict containing voice information

        """
        return {
            "provider": "bedrock",
            "voice_id": self.voice_id,
            "output_format": self.output_format,
            "engine": self.engine,
            "supported_formats": ["mp3", "ogg_vorbis", "pcm"],
            "supported_engines": ["neural", "standard"],
            "max_text_length": 3000,  # Polly limit
            "supported_voices": [
                "Joanna", "Matthew", "Amy", "Brian", "Emma", "Raveena",
                "Aditi", "Astrid", "Bianca", "Carla", "Carmen", "Celine",
                "Chantal", "Conchita", "Cristiano", "Dora", "Hans", "Ines",
                "Ivy", "Jacek", "Jan", "Joey", "Justin", "Karl", "Laura",
                "Lea", "Liam", "Liv", "Lotte", "Lucia", "Lupe", "Mads",
                "Maja", "Marlene", "Mathieu", "Maxim", "Mia", "Miguel",
                "Mizuki", "Naja", "Nicole", "Penelope", "Ruben", "Russell",
                "Salli", "Seoyeon", "Takumi", "Tatyana", "Vicki", "Vitoria",
                "Zeina", "Zhiyu"
            ]
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

        if len(text) > 3000:  # Polly character limit
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
        return [
            "Joanna", "Matthew", "Amy", "Brian", "Emma", "Raveena",
            "Aditi", "Astrid", "Bianca", "Carla", "Carmen", "Celine",
            "Chantal", "Conchita", "Cristiano", "Dora", "Hans", "Ines",
            "Ivy", "Jacek", "Jan", "Joey", "Justin", "Karl", "Laura",
            "Lea", "Liam", "Liv", "Lotte", "Lucia", "Lupe", "Mads",
            "Maja", "Marlene", "Mathieu", "Maxim", "Mia", "Miguel",
            "Mizuki", "Naja", "Nicole", "Penelope", "Ruben", "Russell",
            "Salli", "Seoyeon", "Takumi", "Tatyana", "Vicki", "Vitoria",
            "Zeina", "Zhiyu"
        ]

    async def test_connection(self) -> bool:
        """Test the connection to the TTS service.

        Returns:
            bool: True if connection is successful, False otherwise

        """
        try:
            if not self.polly_client:
                return False

            # Try a simple synthesis to test connection
            test_text = "Test"
            await self.synthesize_speech(test_text)
            return True

        except Exception as e:
            self.logger.error(f"TTS connection test failed: {e}")
            return False
