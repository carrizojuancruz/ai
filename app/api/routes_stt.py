"""STT (Speech-to-Text) API routes.

Provides endpoints for audio transcription using the configured STT provider.
"""

import base64
import logging
from typing import Optional

from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app.services.stt.factory import get_stt_service, is_stt_available

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stt", tags=["STT"])


class TranscriptionResponse(BaseModel):
    """OpenAPI response model for STT transcription results."""

    text: str
    provider: Optional[str] = None
    model: Optional[str] = None


# Module-level parameter singletons to satisfy ruff B008
FILE_PARAM = File(
    None,
    description="Audio file to transcribe (e.g., audio/mpeg, audio/wav)"
)
FILE_B64_PARAM = Body(
    None,
    description=(
        "Base64-encoded audio content. You may provide a raw base64 string or a data URL "
        "like 'data:audio/wav;base64,....'"
    ),
)
MIMETYPE_PARAM = Query(
    None,
    description=(
        "Optional MIME type hint for base64 input (e.g., audio/mpeg, audio/wav). "
        "Ignored if 'file' is provided."
    ),
)
FMT_PARAM = Query(
    None,
    description="Optional response format. If 'text' (default), returns only text and metadata.",
)

@router.post(
    "/transcribe",
    summary="Transcribe an audio file",
    description=(
        "Uploads an audio file and returns the transcribed text using the configured "
        "Speech-to-Text provider. If 'fmt' is omitted or set to 'text', the response "
        "contains only text and metadata. Otherwise, provider-specific raw output may be returned."
    ),
    response_model=TranscriptionResponse,
    responses={
        503: {"description": "STT service not available"},
        500: {"description": "Unexpected server error during transcription"},
    },
)
async def transcribe(
    file: Optional[UploadFile] = FILE_PARAM,
    file_b64: Optional[str] = FILE_B64_PARAM,
    mime_type: Optional[str] = MIMETYPE_PARAM,
    fmt: Optional[str] = FMT_PARAM,
) -> TranscriptionResponse:
    """Transcribe audio provided as multipart file upload or base64 string.

    Args:
        file: Uploaded audio file (multipart/form-data).
        file_b64: Base64-encoded audio content (raw base64 or data URL).
        mime_type: Optional MIME type when using base64 input.
        fmt: Optional response format. If 'text' (default), returns only text and metadata.

    Returns:
        Dict containing at least {"text": str, "provider": str, "model": Optional[str]}

    """
    try:
        if not is_stt_available():
            raise HTTPException(status_code=503, detail="STT service not available")

        service = get_stt_service()
        if service is None:
            raise HTTPException(status_code=503, detail="STT service not available")

        audio_bytes: Optional[bytes] = None
        detected_mime: Optional[str] = None

        # Prefer multipart file if provided
        if file is not None:
            audio_bytes = await file.read()
            detected_mime = getattr(file, "content_type", None)
        elif file_b64:
            # Support data URL format: data:audio/wav;base64,XXXX
            b64_str = file_b64.strip()
            if b64_str.startswith("data:"):
                try:
                    header, b64_payload = b64_str.split(",", 1)
                except ValueError as err:
                    raise HTTPException(status_code=400, detail="Invalid data URL format for base64 audio") from err
                # Extract MIME type from header if present
                try:
                    mime_part = header.split(":", 1)[1]
                    detected_mime = mime_part.split(";", 1)[0] or None
                except Exception:
                    detected_mime = None
                b64_str = b64_payload
            # Decode base64
            try:
                audio_bytes = base64.b64decode(b64_str, validate=True)
            except Exception as err:
                raise HTTPException(status_code=400, detail="Invalid base64 audio content") from err
        else:
            raise HTTPException(status_code=400, detail="No audio provided. Supply 'file' or 'file_b64'.")

        # Choose mime type preference: detected from file/data URL, then query param
        final_mime = detected_mime or mime_type

        result = await service.transcribe(audio_bytes, mime_type=final_mime)

        # Simple format handling: if fmt == "text", return only text plus meta
        if fmt == "text" or fmt is None:
            return TranscriptionResponse(
                text=result.get("text", ""),
                provider=result.get("provider"),
                model=result.get("model"),
            )
        # When not 'text', return the provider raw result; OpenAPI model does not strictly apply
        # so we bypass Pydantic by returning the raw dict.
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("STT transcription failed")
        raise HTTPException(status_code=500, detail=f"STT transcription failed: {str(e)}") from e
