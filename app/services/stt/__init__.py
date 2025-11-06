"""Speech-to-Text (STT) service module.

This module provides a unified interface for speech-to-text transcription across
different providers (e.g., OpenAI, AWS Bedrock Transcribe, etc.).
"""

from .base import STTService
from .events import (
    TRANSCRIPT_EVENTS,
    create_transcript_chunk_event,
    create_transcript_completed_event,
    create_transcript_error_event,
    create_transcript_start_event,
)
from .factory import get_stt_service

__all__ = [
    "STTService",
    "get_stt_service",
    "create_transcript_start_event",
    "create_transcript_chunk_event",
    "create_transcript_completed_event",
    "create_transcript_error_event",
    "TRANSCRIPT_EVENTS",
]
