"""Audio SSE routes for streaming audio synthesis.

This module provides Server-Sent Events endpoints for audio streaming,
separate from the main text conversation channels.
"""

import asyncio
import json
import logging
import time
from typing import AsyncGenerator

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

from app.core.app_state import drop_audio_queue, get_audio_queue
from app.services.audio_service import get_audio_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/audio", tags=["Audio SSE"])


@router.get("/sse/{thread_id}")
async def audio_sse(thread_id: str, request: Request) -> StreamingResponse:
    """Audio SSE endpoint for streaming audio synthesis.

    This endpoint provides a separate channel for audio events,
    independent from the main text conversation flow.

    Args:
        thread_id: Unique thread identifier
        request: FastAPI request object

    Returns:
        StreamingResponse: SSE stream with audio events

    """
    audio_queue = get_audio_queue(thread_id)

    async def audio_event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events for audio streaming."""
        try:
            logger.info(f"[AUDIO SSE] Starting audio stream for thread_id: {thread_id}")

            # Check if there's a buffer with existing audio chunks
            audio_service = get_audio_service()
            buffer = audio_service.get_audio_buffer(thread_id) if audio_service else None

            if buffer and buffer.is_completed():
                # Send all buffered chunks first
                logger.info(f"[AUDIO SSE] Sending {len(buffer.get_chunks())} buffered chunks for thread_id: {thread_id}")
                for chunk in buffer.get_chunks():
                    if isinstance(chunk, dict) and "event" in chunk:
                        event_name = chunk.get("event")
                        payload = chunk.get("data", {})
                        payload["thread_id"] = thread_id

                        yield f"event: {event_name}\n"
                        yield f"data: {json.dumps(payload)}\n\n"

                        logger.debug(f"[AUDIO SSE] Sent buffered event {event_name} for thread_id: {thread_id}")

                # Mark buffer as consumed (optional - could keep for other clients)
                logger.info(f"[AUDIO SSE] Finished sending buffered chunks for thread_id: {thread_id}")
            elif buffer and not buffer.is_completed():
                # Buffer exists but not completed yet - send what we have and continue streaming
                logger.info(f"[AUDIO SSE] Sending partial buffer ({len(buffer.get_chunks())} chunks) for thread_id: {thread_id}")
                for chunk in buffer.get_chunks():
                    if isinstance(chunk, dict) and "event" in chunk:
                        event_name = chunk.get("event")
                        payload = chunk.get("data", {})
                        payload["thread_id"] = thread_id

                        yield f"event: {event_name}\n"
                        yield f"data: {json.dumps(payload)}\n\n"

                        logger.debug(f"[AUDIO SSE] Sent partial buffered event {event_name} for thread_id: {thread_id}")

            # Continue with real-time streaming
            while True:
                if await request.is_disconnected():
                    logger.info(f"[AUDIO SSE] Client disconnected for thread_id: {thread_id}")
                    break

                try:
                    item = await asyncio.wait_for(audio_queue.get(), timeout=10.0)
                except TimeoutError:
                    # Send keepalive ping
                    yield f"event: ping\ndata: {json.dumps({'timestamp': asyncio.get_event_loop().time()})}\n\n"
                    continue

                if isinstance(item, dict) and "event" in item:
                    event_name = item.get("event")
                    payload = item.get("data", {})

                    # Add thread_id to payload for client context
                    payload["thread_id"] = thread_id

                    yield f"event: {event_name}\n"
                    yield f"data: {json.dumps(payload)}\n\n"

                    logger.debug(f"[AUDIO SSE] Sent real-time event {event_name} for thread_id: {thread_id}")
                else:
                    # Handle non-event data
                    yield f"data: {json.dumps(item)}\n\n"

        except Exception as e:
            logger.error(f"[AUDIO SSE] Error in audio stream for thread_id {thread_id}: {e}")
            yield f"event: audio.error\ndata: {json.dumps({'error': str(e), 'thread_id': thread_id})}\n\n"
        finally:
            # Clean up audio queue when client disconnects
            logger.info(f"[AUDIO SSE] Cleaning up audio queue for thread_id: {thread_id}")
            drop_audio_queue(thread_id)

    return StreamingResponse(
        audio_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


@router.get("/health")
async def audio_health_check() -> dict:
    """Health check for audio service.

    Returns:
        dict: Health status of audio service

    """
    return {
        "service": "audio-sse",
        "status": "healthy",
        "description": "Audio SSE service is running"
    }


@router.post("/cleanup-buffers")
async def cleanup_audio_buffers() -> dict:
    """Clean up expired audio buffers.

    Returns:
        dict: Cleanup results

    """
    try:
        audio_service = get_audio_service()
        if not audio_service:
            return {
                "status": "error",
                "message": "Audio service not available"
            }

        cleaned_count = await audio_service.cleanup_expired_buffers()

        return {
            "status": "success",
            "message": f"Cleaned up {cleaned_count} expired buffers",
            "cleaned_count": cleaned_count
        }
    except Exception as e:
        logger.error(f"Error cleaning up audio buffers: {e}")
        return {
            "status": "error",
            "message": f"Failed to clean up buffers: {str(e)}"
        }


@router.get("/buffers/status")
async def get_audio_buffers_status() -> dict:
    """Get status of all audio buffers.

    Returns:
        dict: Status of all audio buffers

    """
    try:
        audio_service = get_audio_service()
        if not audio_service:
            return {
                "status": "error",
                "message": "Audio service not available"
            }

        buffers_info = {}
        current_time = time.time()
        for thread_id, buffer in audio_service.audio_buffers.items():
            buffers_info[thread_id] = {
                "chunk_count": len(buffer.get_chunks()),
                "created_at": buffer.created_at,
                "ttl": buffer.ttl,
                "is_expired": buffer.is_expired(),
                "is_completed": buffer.is_completed(),
                "age_seconds": current_time - buffer.created_at
            }

        return {
            "status": "success",
            "total_buffers": len(audio_service.audio_buffers),
            "buffers": buffers_info
        }
    except Exception as e:
        logger.error(f"Error getting audio buffers status: {e}")
        return {
            "status": "error",
            "message": f"Failed to get buffer status: {str(e)}"
        }


@router.delete("/cleanup/{thread_id}")
async def cleanup_audio_thread(thread_id: str) -> dict:
    """Clean up a thread_id from the audio system."""
    from app.services.audio_service import cleanup_audio_thread as cleanup_service

    # Use the service function
    result = await cleanup_service(thread_id)

    # Clean up the SSE queue for complete cleanup
    try:
        from app.core.app_state import drop_sse_queue
        drop_sse_queue(thread_id)
        logger.info(f"[AUDIO CLEANUP] Removed SSE queue for thread_id: {thread_id}")
    except Exception as e:
        logger.warning(f"[AUDIO CLEANUP] Failed to remove SSE queue for thread_id {thread_id}: {e}")

    return result
