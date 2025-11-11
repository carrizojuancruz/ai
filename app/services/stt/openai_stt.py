import io
import logging
from typing import Any, AsyncIterator, Dict, Optional

import httpx

from app.core.config import config

from .base import STTService, STTServiceError

logger = logging.getLogger(__name__)


class OpenAISTTService(STTService):
    """OpenAI STT service implementation using OpenAI's Whisper transcription API."""

    def __init__(self):
        super().__init__(model=config.OPENAI_STT_MODEL, sample_rate=16000)
        if not getattr(config, "OPENAI_API_KEY", None):
            raise STTServiceError("Missing OPENAI_API_KEY", provider="openai")

        self.model = config.OPENAI_STT_MODEL or "whisper-1"
        self.openai_client = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize the OpenAI client."""
        try:
            self.openai_client = httpx.AsyncClient(timeout=60.0)
            self.logger.info(f"OpenAI STT service initialized with model={self.model}")
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenAI STT client: {e}")
            raise STTServiceError(f"Failed to initialize OpenAI client: {e}", provider="openai") from e

    async def validate_audio(self, audio_bytes: bytes, mime_type: Optional[str] = None) -> bool:
        """Validate audio payload for size/format constraints.

        Args:
            audio_bytes: The audio data to validate
            mime_type: Optional MIME type of the audio

        Returns:
            bool: True if audio is valid, False otherwise

        """
        if not audio_bytes:
            self.logger.warning("Empty audio data provided")
            return False

        # OpenAI has a 25MB file size limit
        max_size = 25 * 1024 * 1024  # 25MB in bytes
        if len(audio_bytes) > max_size:
            self.logger.warning(f"Audio file too large: {len(audio_bytes)} bytes (max: {max_size})")
            return False

        return True

    async def transcribe(self, audio_bytes: bytes, mime_type: Optional[str] = None) -> Dict[str, Any]:
        """Transcribe audio using OpenAI's transcription API.

        Args:
            audio_bytes: The audio data to transcribe
            mime_type: Optional MIME type of the audio (e.g., 'audio/mp3', 'audio/wav')

        Returns:
            Dict containing transcription result with at least {"text": str}

        Raises:
            STTServiceError: If transcription fails

        """
        if not self.openai_client:
            raise STTServiceError("OpenAI client not initialized", provider="openai")

        if not await self.validate_audio(audio_bytes, mime_type):
            raise STTServiceError("Invalid audio payload", provider="openai")

        try:
            self.logger.info(f"Transcribing audio of size: {len(audio_bytes)} bytes")

            # Determine file extension from mime_type
            file_extension = self._get_file_extension(mime_type)

            # Call the async transcription method
            result = await self._transcribe_async(audio_bytes, file_extension)

            self.logger.info(f"Successfully transcribed audio, text length: {len(result.get('text', ''))} characters")

            return result

        except Exception as e:
            self.logger.error(f"STT transcription failed: {e}")
            raise STTServiceError(f"Transcription failed: {str(e)}", provider="openai") from e

    async def _transcribe_async(self, audio_bytes: bytes, file_extension: str) -> Dict[str, Any]:
        """Make async OpenAI transcription API request.

        Args:
            audio_bytes: The audio data to transcribe
            file_extension: File extension for the audio format

        Returns:
            Dict containing a transcription result

        """
        # Prepare the file for multipart upload
        files = {
            'file': (f'audio.{file_extension}', io.BytesIO(audio_bytes), f'audio/{file_extension}')
        }

        # Prepare form data
        data = {
            'model': self.model,
            'language': 'en'
        }

        response = await self.openai_client.post(
            "https://api.openai.com/v1/audio/transcriptions",
            files=files,
            data=data,
            headers={
                "Authorization": f"Bearer {config.OPENAI_API_KEY}",
            },
        )

        response.raise_for_status()

        result = response.json()

        # Return standardized format
        return {
            "text": result.get("text", ""),
            "provider": "openai",
            "model": self.model,
        }

    @staticmethod
    def _get_file_extension(mime_type: Optional[str]) -> str:
        """Get file extension from the MIME type.

        Args:
            mime_type: The MIME type of the audio file

        Returns:
            File extension (defaults to 'mp3' if unknown)

        """
        mime_to_ext = {
            'audio/mp3': 'mp3',
            'audio/mpeg': 'mp3',
            'audio/wav': 'wav',
            'audio/wave': 'wav',
            'audio/x-wav': 'wav',
            'audio/webm': 'webm',
            'audio/mp4': 'mp4',
            'audio/m4a': 'm4a',
            'audio/x-m4a': 'm4a',
        }

        if mime_type:
            return mime_to_ext.get(mime_type.lower(), 'mp3')
        return 'mp3'

    async def transcribe_stream(self, audio_stream: AsyncIterator[bytes], mime_type: Optional[str] = None) -> \
    AsyncIterator[Dict[str, Any]]:
        """Streaming transcription isn't supported by OpenAI API.

        Raises:
            STTServiceError: Always, as streaming is not implemented

        """
        raise STTServiceError("Streaming STT not implemented for OpenAI", provider="openai")

    async def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current STT model/provider.

        Returns:
            Dict containing model information

        """
        return {
            "provider": "openai",
            "model": self.model,
            "sample_rate": self.sample_rate,
            "max_file_size": 25 * 1024 * 1024,  # 25MB
            "supported_formats": ["mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm"],
        }

    async def test_connection(self) -> bool:
        """Test the connection to the STT service.

        Returns:
            bool: True if connection is successful, False otherwise

        """
        try:
            if not self.openai_client:
                return False

            # Just verify the client is initialized and API key is set
            return bool(config.OPENAI_API_KEY)

        except Exception as e:
            self.logger.error(f"STT connection test failed: {e}")
            return False
