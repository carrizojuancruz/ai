"""Audio Service for handling TTS synthesis and streaming.

This service listens for text completion events from the supervisor
and coordinates audio synthesis and streaming through a separate SSE channel.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional

from app.services.tts import get_tts_service
from app.services.tts.events import (
    create_audio_chunk_event,
    create_audio_completed_event,
    create_audio_error_event,
    create_audio_start_event,
)

logger = logging.getLogger(__name__)


class AudioBuffer:
    """Temporary buffer for audio chunks with TTL."""

    def __init__(self, ttl_seconds: int = 300):  # 5 minutes default
        self.chunks: List[Dict] = []
        self.created_at = time.time()
        self.ttl = ttl_seconds
        self.completed = False

    def add_chunk(self, chunk: Dict) -> None:
        """Add a chunk to the buffer."""
        self.chunks.append(chunk)
        logger.debug(f"[AUDIO BUFFER] Added chunk, total: {len(self.chunks)}")

    def is_expired(self) -> bool:
        """Check if buffer has expired."""
        return time.time() - self.created_at > self.ttl

    def get_chunks(self) -> List[Dict]:
        """Get all chunks from buffer."""
        return self.chunks.copy()

    def mark_completed(self) -> None:
        """Mark buffer as completed."""
        self.completed = True
        logger.debug(f"[AUDIO BUFFER] Marked as completed with {len(self.chunks)} chunks")

    def is_completed(self) -> bool:
        """Check if buffer is completed."""
        return self.completed


class AudioService:
    """Service for handling audio synthesis and streaming."""

    def __init__(self):
        self.active_listeners: dict[str, asyncio.Task] = {}
        self.tts_service = get_tts_service()
        self.audio_buffers: Dict[str, AudioBuffer] = {}  # Buffer for thread_id
        self.buffer_ttl = 300  # 5 minutes TTL

    async def start_listening_for_thread(self, thread_id: str) -> None:
        """Start audio service for a specific thread (simplified - no longer needed).

        Args:
            thread_id: Unique thread identifier

        """
        logger.info(f"[AUDIO SERVICE] Audio service ready for thread_id: {thread_id}")

    async def stop_listening_for_thread(self, thread_id: str) -> None:
        """Stop audio service for a specific thread.

        Args:
            thread_id: Unique thread identifier

        """
        logger.info(f"[AUDIO SERVICE] Audio service stopped for thread_id: {thread_id}")

    async def _synthesize_and_stream_audio(
        self,
        thread_id: str,
        text: str,
        voice_id: str,
        output_format: str,
        audio_queue: asyncio.Queue
    ) -> None:
        """Synthesize audio and stream it through audio queue.

        Args:
            thread_id: Unique thread identifier
            text: Text to synthesize
            voice_id: Voice identifier
            output_format: Audio format
            audio_queue: Audio queue for streaming

        """
        try:
            if not self.tts_service:
                logger.error("[AUDIO SERVICE] TTS service not available")
                await audio_queue.put(create_audio_error_event(
                    "TTS service not available",
                    "TTS_SERVICE_UNAVAILABLE"
                ))
                return

            # Create audio buffer for this thread
            self.audio_buffers[thread_id] = AudioBuffer(ttl_seconds=self.buffer_ttl)
            logger.info(f"[AUDIO SERVICE] Created audio buffer for thread_id: {thread_id}")

            # Send audio.start event
            start_event = create_audio_start_event(text, voice_id, output_format)
            await audio_queue.put(start_event)
            self.audio_buffers[thread_id].add_chunk(start_event)
            logger.info(f"[AUDIO SERVICE] Sent audio.start for thread_id: {thread_id}")

            # Synthesize audio
            logger.info(f"[AUDIO SERVICE] Starting audio synthesis for thread_id: {thread_id}")
            audio_data = await self.tts_service.synthesize_speech(text)

            # Stream audio in chunks
            chunk_size = 8192  # 8KB chunks
            total_chunks = (len(audio_data) + chunk_size - 1) // chunk_size

            logger.info(f"[AUDIO SERVICE] Streaming {total_chunks} audio chunks for thread_id: {thread_id}")

            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i + chunk_size]
                chunk_index = i // chunk_size

                chunk_event = create_audio_chunk_event(chunk, chunk_index, total_chunks)

                # Send to queue for real-time clients
                await audio_queue.put(chunk_event)

                # Store in buffer for late-connecting clients
                self.audio_buffers[thread_id].add_chunk(chunk_event)

                # Small delay to simulate streaming
                await asyncio.sleep(0.01)

            # Send audio.completed event
            duration = len(audio_data) / 16000  # Rough estimate for MP3
            completed_event = create_audio_completed_event(
                duration, output_format, len(audio_data)
            )
            await audio_queue.put(completed_event)
            self.audio_buffers[thread_id].add_chunk(completed_event)
            self.audio_buffers[thread_id].mark_completed()

            logger.info(f"[AUDIO SERVICE] Audio synthesis completed for thread_id: {thread_id}, size: {len(audio_data)} bytes")

            # Schedule buffer cleanup
            asyncio.create_task(self._cleanup_buffer_later(thread_id))

        except Exception as e:
            logger.error(f"[AUDIO SERVICE] Error synthesizing audio for thread_id {thread_id}: {e}")
            error_event = create_audio_error_event(
                f"Audio synthesis failed: {str(e)}",
                "SYNTHESIS_ERROR"
            )
            await audio_queue.put(error_event)
            if thread_id in self.audio_buffers:
                self.audio_buffers[thread_id].add_chunk(error_event)
                self.audio_buffers[thread_id].mark_completed()

    def get_audio_buffer(self, thread_id: str) -> Optional[AudioBuffer]:
        """Get audio buffer for a thread if it exists and is not expired.

        Args:
            thread_id: Unique thread identifier

        Returns:
            AudioBuffer if exists and not expired, None otherwise

        """
        if thread_id not in self.audio_buffers:
            return None

        buffer = self.audio_buffers[thread_id]
        if buffer.is_expired():
            logger.info(f"[AUDIO SERVICE] Buffer expired for thread_id: {thread_id}")
            del self.audio_buffers[thread_id]
            return None

        return buffer

    async def _cleanup_buffer_later(self, thread_id: str) -> None:
        """Clean up buffer after TTL expires.

        Args:
            thread_id: Unique thread identifier

        """
        await asyncio.sleep(self.buffer_ttl)
        if thread_id in self.audio_buffers:
            logger.info(f"[AUDIO SERVICE] Cleaning up expired buffer for thread_id: {thread_id}")
            del self.audio_buffers[thread_id]

    async def cleanup_expired_buffers(self) -> int:
        """Clean up all expired buffers.

        Returns:
            Number of buffers cleaned up

        """
        expired_threads = []
        for thread_id, buffer in self.audio_buffers.items():
            if buffer.is_expired():
                expired_threads.append(thread_id)

        for thread_id in expired_threads:
            del self.audio_buffers[thread_id]
            logger.info(f"[AUDIO SERVICE] Cleaned up expired buffer for thread_id: {thread_id}")

        return len(expired_threads)

    async def cleanup(self) -> None:
        """Clean up all active listeners and buffers."""
        for thread_id, task in self.active_listeners.items():
            task.cancel()
            logger.info(f"[AUDIO SERVICE] Cancelled listener for thread_id: {thread_id}")

        self.active_listeners.clear()
        self.audio_buffers.clear()
        logger.info("[AUDIO SERVICE] All listeners and buffers cleaned up")


# Global audio service instance
_audio_service: Optional[AudioService] = None


def get_audio_service() -> AudioService:
    """Get the global audio service instance.

    Returns:
        AudioService: Global audio service instance

    """
    global _audio_service
    if _audio_service is None:
        _audio_service = AudioService()
    return _audio_service


async def start_audio_service_for_thread(thread_id: str) -> None:
    """Start audio service for a specific thread.

    Args:
        thread_id: Unique thread identifier

    """
    service = get_audio_service()
    await service.start_listening_for_thread(thread_id)


async def stop_audio_service_for_thread(thread_id: str) -> None:
    """Stop audio service for a specific thread.

    Args:
        thread_id: Unique thread identifier

    """
    service = get_audio_service()
    await service.stop_listening_for_thread(thread_id)


async def cleanup_audio_thread(thread_id: str) -> dict:
    """Clean up a specific thread_id from the audio system.

    Args:
        thread_id: Unique thread identifier

    Returns:
        dict: Status of the cleanup

    """
    try:
        logger.info(f"[AUDIO SERVICE] Starting cleanup for thread_id: {thread_id}")

        service = get_audio_service()
        if not service:
            return {
                "status": "error",
                "message": "Audio service not available"
            }

        # Clean up audio buffer if it exists
        buffer_cleaned = False
        if thread_id in service.audio_buffers:
            del service.audio_buffers[thread_id]
            buffer_cleaned = True
            logger.info(f"[AUDIO SERVICE] Removed audio buffer for thread_id: {thread_id}")

        # Clean up audio queue
        from app.core.app_state import drop_audio_queue
        drop_audio_queue(thread_id)
        logger.info(f"[AUDIO SERVICE] Removed audio queue for thread_id: {thread_id}")

        return {
            "status": "success",
            "thread_id": thread_id,
            "buffer_cleaned": buffer_cleaned,
            "message": f"Audio cleanup completed for thread_id: {thread_id}"
        }

    except Exception as e:
        logger.error(f"[AUDIO SERVICE] Error cleaning up thread_id {thread_id}: {e}")
        return {
            "status": "error",
            "thread_id": thread_id,
            "message": f"Failed to cleanup thread_id: {str(e)}"
        }
