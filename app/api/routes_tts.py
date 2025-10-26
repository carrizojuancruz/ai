"""TTS (Text-to-Speech) API routes for testing and debugging.

This module provides endpoints for testing TTS functionality,
including synthesis, voice information, and service health checks.
"""

import base64
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.tts import get_tts_service
from app.services.tts.events import (
    create_audio_chunk_event,
    create_audio_completed_event,
    create_audio_error_event,
    create_audio_start_event,
)
from app.services.tts.factory import is_tts_available, test_tts_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tts", tags=["TTS"])


class TTSTestRequest(BaseModel):
    """Request model for TTS test endpoint."""

    text: str
    voice_id: Optional[str] = None
    output_format: Optional[str] = None


class TTSTestResponse(BaseModel):
    """Response model for TTS test endpoint."""

    success: bool
    message: str
    audio_data: Optional[str] = None  # Base64 encoded
    duration: Optional[float] = None
    size_bytes: Optional[int] = None
    voice_info: Optional[Dict[str, Any]] = None


class TTSHealthResponse(BaseModel):
    """Response model for TTS health check."""

    available: bool
    provider: Optional[str] = None
    voice_info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@router.get("/health", response_model=TTSHealthResponse)
async def tts_health_check():
    """Check TTS service health and configuration.

    Returns:
        TTSHealthResponse: Health status and configuration info

    """
    try:
        if not is_tts_available():
            return TTSHealthResponse(
                available=False,
                error="TTS service not available or disabled"
            )

        service = get_tts_service()
        if not service:
            return TTSHealthResponse(
                available=False,
                error="TTS service instance not available"
            )

        # Test connection
        connection_ok = await test_tts_service()
        if not connection_ok:
            return TTSHealthResponse(
                available=False,
                provider=service.get_provider_name(),
                error="TTS service connection test failed"
            )

        # Get voice info
        voice_info = await service.get_voice_info()

        return TTSHealthResponse(
            available=True,
            provider=service.get_provider_name(),
            voice_info=voice_info
        )

    except Exception as e:
        logger.error(f"TTS health check failed: {e}")
        return TTSHealthResponse(
            available=False,
            error=f"Health check failed: {str(e)}"
        )


@router.post("/test", response_model=TTSTestResponse)
async def test_tts_synthesis(request: TTSTestRequest):
    """Test TTS synthesis with provided text.

    Args:
        request: TTS test request with text and optional parameters

    Returns:
        TTSTestResponse: Synthesis result with audio data

    """
    try:
        if not is_tts_available():
            raise HTTPException(
                status_code=503,
                detail="TTS service not available"
            )

        service = get_tts_service()
        if not service:
            raise HTTPException(
                status_code=503,
                detail="TTS service instance not available"
            )

        # Validate text
        if not request.text or not request.text.strip():
            raise HTTPException(
                status_code=400,
                detail="Text cannot be empty"
            )

        if len(request.text) > 3000:  # Polly limit
            raise HTTPException(
                status_code=400,
                detail="Text too long (max 3000 characters)"
            )

        logger.info(f"Testing TTS synthesis for text: '{request.text[:50]}...'")

        # Synthesize speech
        audio_data = await service.synthesize_speech(request.text)

        # Get voice info
        voice_info = await service.get_voice_info()

        # Encode audio as base64
        audio_base64 = base64.b64encode(audio_data).decode()

        # Estimate duration (rough calculation)
        duration = len(audio_data) / 16000  # Rough estimate for MP3

        logger.info(f"TTS synthesis successful: {len(audio_data)} bytes, ~{duration:.2f}s")

        return TTSTestResponse(
            success=True,
            message="TTS synthesis successful",
            audio_data=audio_base64,
            duration=duration,
            size_bytes=len(audio_data),
            voice_info=voice_info
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS synthesis test failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"TTS synthesis failed: {str(e)}"
        )


@router.get("/voices")
async def get_available_voices():
    """Get list of available voices for the current TTS provider.

    Returns:
        Dict containing available voices and provider info

    """
    try:
        if not is_tts_available():
            raise HTTPException(
                status_code=503,
                detail="TTS service not available"
            )

        service = get_tts_service()
        if not service:
            raise HTTPException(
                status_code=503,
                detail="TTS service instance not available"
            )

        voices = service.get_available_voices()
        voice_info = await service.get_voice_info()

        return {
            "provider": service.get_provider_name(),
            "current_voice": service.voice_id,
            "available_voices": voices,
            "voice_info": voice_info
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get available voices: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get voices: {str(e)}"
        )


@router.get("/events/sample")
async def get_sample_events():
    """Get sample SSE events for TTS functionality.

    Returns:
        Dict containing sample events for testing

    """
    try:
        sample_text = "Hello, this is a test of the TTS system."

        # Create sample events
        start_event = create_audio_start_event(
            text=sample_text,
            voice_id="Joanna",
            output_format="mp3"
        )

        # Sample audio chunk (empty for demo)
        chunk_event = create_audio_chunk_event(
            audio_data=b"sample_audio_data",
            chunk_index=0,
            total_chunks=1
        )

        completed_event = create_audio_completed_event(
            duration=2.5,
            output_format="mp3",
            size_bytes=1024
        )

        error_event = create_audio_error_event(
            error_message="Sample error for testing"
        )

        return {
            "sample_events": {
                "start": start_event,
                "chunk": chunk_event,
                "completed": completed_event,
                "error": error_event
            },
            "description": "Sample SSE events for TTS functionality"
        }

    except Exception as e:
        logger.error(f"Failed to generate sample events: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate sample events: {str(e)}"
        )


@router.get("/config")
async def get_tts_config():
    """Get current TTS configuration.

    Returns:
        Dict containing current TTS configuration

    """
    try:
        from app.core.config import config

        return {
            "audio_enabled": config.AUDIO_ENABLED,
            "tts_provider": config.TTS_PROVIDER,
            "tts_voice_id": config.TTS_VOICE_ID,
            "tts_output_format": config.TTS_OUTPUT_FORMAT,
            "tts_engine": config.TTS_ENGINE,
            "tts_chunk_size": config.TTS_CHUNK_SIZE,
            "service_available": is_tts_available()
        }

    except Exception as e:
        logger.error(f"Failed to get TTS config: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get config: {str(e)}"
        )
