"""SSE Events for Text-to-Speech (TTS) functionality.

This module defines the Server-Sent Events (SSE) event types and data structures
used for streaming audio generation and delivery.
"""

from typing import Any, Dict, Optional


def create_audio_start_event(text: str, voice_id: str, output_format: str) -> Dict[str, Any]:
    """Create an audio.start SSE event.

    Args:
        text: The text to be converted to speech
        voice_id: The voice identifier to use for synthesis
        output_format: The audio format (e.g., 'mp3', 'wav')

    Returns:
        Dict containing the SSE event structure

    """
    return {
        "event": "audio.start",
        "data": {
            "text": text,
            "voice_id": voice_id,
            "format": output_format
        }
    }


def create_audio_chunk_event(audio_data: bytes, chunk_index: int, total_chunks: int) -> Dict[str, Any]:
    """Create an audio.chunk SSE event.

    Args:
        audio_data: The audio chunk data (base64 encoded)
        chunk_index: The index of this chunk (0-based)
        total_chunks: Total number of chunks

    Returns:
        Dict containing the SSE event structure

    """
    import base64

    return {
        "event": "audio.chunk",
        "data": {
            "audio_data": base64.b64encode(audio_data).decode(),
            "chunk_index": chunk_index,
            "total_chunks": total_chunks
        }
    }


def create_audio_completed_event(duration: float, output_format: str, size_bytes: int) -> Dict[str, Any]:
    """Create an audio.completed SSE event.

    Args:
        duration: Audio duration in seconds
        output_format: The audio format
        size_bytes: Total size of the audio data in bytes

    Returns:
        Dict containing the SSE event structure

    """
    return {
        "event": "audio.completed",
        "data": {
            "duration": duration,
            "format": output_format,
            "size_bytes": size_bytes
        }
    }


def create_audio_error_event(error_message: str, error_code: Optional[str] = None) -> Dict[str, Any]:
    """Create an audio.error SSE event.

    Args:
        error_message: Human-readable error message
        error_code: Optional error code for programmatic handling

    Returns:
        Dict containing the SSE event structure

    """
    data = {"error": error_message}
    if error_code:
        data["error_code"] = error_code

    return {
        "event": "audio.error",
        "data": data
    }


# Event type constants for easy reference
AUDIO_EVENTS = {
    "START": "audio.start",
    "CHUNK": "audio.chunk",
    "COMPLETED": "audio.completed",
    "ERROR": "audio.error"
}
