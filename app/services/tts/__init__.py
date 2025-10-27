"""Text-to-Speech (TTS) service module.

This module provides a unified interface for text-to-speech synthesis across
different providers (AWS Bedrock/Polly, Google Cloud, Azure, etc.).
"""

from .base import TTSService
from .events import (
    AUDIO_EVENTS,
    create_audio_chunk_event,
    create_audio_completed_event,
    create_audio_error_event,
    create_audio_start_event,
)
from .factory import get_tts_service

__all__ = [
    "TTSService",
    "get_tts_service",
    "create_audio_start_event",
    "create_audio_chunk_event",
    "create_audio_completed_event",
    "create_audio_error_event",
    "AUDIO_EVENTS"
]
