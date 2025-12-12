from __future__ import annotations

import asyncio
import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Optional, TypedDict

from app.core.config import config

logger = logging.getLogger(__name__)

MAX_COLD_PATH_WORKERS: int = config.MEMORY_COLD_PATH_MAX_WORKERS
COLD_PATH_MAX_RETRIES: int = config.MEMORY_COLD_PATH_MAX_RETRIES
COLD_PATH_RETRY_BACKOFF_SECONDS: float = config.MEMORY_COLD_PATH_RETRY_BACKOFF_SECONDS
THREAD_STATE_TTL_SECONDS: int = config.MEMORY_COLD_PATH_THREAD_STATE_TTL_SECONDS
THREAD_STATE_CLEANUP_INTERVAL_SECONDS: int = config.MEMORY_COLD_PATH_THREAD_STATE_CLEANUP_INTERVAL_SECONDS


class _TurnPayload(TypedDict):
    thread_id: str
    user_id: str
    user_context: dict[str, Any]
    conversation_window: list[dict[str, Any]]
    event_loop: asyncio.AbstractEventLoop
    store: Any


class MemoryColdPathManager:
    """Manages cold-path memory creation jobs using a bounded threadpool.

    Serializes jobs per thread_id to avoid concurrent merge races.
    Coalesces jobs per thread_id (keeps only latest payload).
    Emits SSE events safely from worker threads.
    Retries failures with bounded backoff.
    """

    def __init__(self, max_workers: int = MAX_COLD_PATH_WORKERS) -> None:
        """Initialize the cold-path manager with a bounded threadpool.

        Args:
            max_workers: Maximum number of worker threads (default from config).

        """
        self._executor: ThreadPoolExecutor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="memory-cold-path",
        )
        self._latest_payload: dict[str, _TurnPayload] = {}
        self._runners: dict[str, Future[None]] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._last_seen_at: dict[str, float] = {}
        self._last_cleanup_at: float = time.time()
        self._lock = threading.Lock()

    def _get_thread_lock(self, thread_id: str) -> threading.Lock:
        """Get or create a lock for a specific thread_id."""
        with self._lock:
            if thread_id not in self._locks:
                self._locks[thread_id] = threading.Lock()
            return self._locks[thread_id]

    def _touch_thread(self, thread_id: str, now: float) -> None:
        self._last_seen_at[thread_id] = now

    def _cleanup_stale_thread_state(self, now: float) -> None:
        stale_thread_ids: list[str] = []
        for thread_id, last_seen in self._last_seen_at.items():
            if (now - last_seen) <= THREAD_STATE_TTL_SECONDS:
                continue
            if thread_id in self._runners:
                continue
            if thread_id in self._latest_payload:
                continue
            stale_thread_ids.append(thread_id)

        for thread_id in stale_thread_ids:
            self._locks.pop(thread_id, None)
            self._last_seen_at.pop(thread_id, None)

    def submit_turn(
        self,
        thread_id: str,
        user_id: str,
        user_context: dict[str, Any],
        conversation_window: list[dict[str, Any]],
        store: Any,
        event_loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        """Submit a cold-path memory job for a completed turn.

        Args:
            thread_id: Thread identifier (used for serialization).
            user_id: User identifier.
            user_context: Fresh user context snapshot.
            conversation_window: Recent conversation messages (last N turns).
            store: Vector store instance used by the cold-path jobs.
            event_loop: Optional event loop for SSE emission (if None, gets current loop).

        """
        if not thread_id:
            logger.warning("memory.cold_path.submit.skip: thread_id missing")
            return

        if event_loop is None:
            try:
                event_loop = asyncio.get_running_loop()
            except RuntimeError:
                logger.warning("memory.cold_path.submit.skip: no event loop available")
                return

        if not user_id:
            logger.warning("memory.cold_path.submit.skip: user_id missing thread_id=%s", thread_id)
            return

        if store is None:
            logger.warning("memory.cold_path.submit.skip: store missing thread_id=%s user_id=%s", thread_id, user_id)
            return

        now = time.time()
        payload: _TurnPayload = {
            "thread_id": thread_id,
            "user_id": user_id,
            "user_context": user_context,
            "conversation_window": conversation_window,
            "event_loop": event_loop,
            "store": store,
        }

        with self._lock:
            self._latest_payload[thread_id] = payload
            self._touch_thread(thread_id, now)

            if (now - self._last_cleanup_at) >= THREAD_STATE_CLEANUP_INTERVAL_SECONDS:
                self._cleanup_stale_thread_state(now)
                self._last_cleanup_at = now

            existing_runner = self._runners.get(thread_id)
            should_start_runner = existing_runner is None or existing_runner.done()

            if should_start_runner:
                runner = self._executor.submit(self._run_thread_runner, thread_id)
                self._runners[thread_id] = runner

        logger.debug("memory.cold_path.submitted: thread_id=%s user_id=%s", thread_id, user_id)

    def _run_thread_runner(self, thread_id: str) -> None:
        """Run the latest queued cold-path payload for a thread until no payload remains."""
        thread_lock = self._get_thread_lock(thread_id)
        try:
            while True:
                with self._lock:
                    payload = self._latest_payload.pop(thread_id, None)
                    self._touch_thread(thread_id, time.time())

                if payload is None:
                    return

                with thread_lock:
                    self._run_payload_with_retries(payload)
        finally:
            with self._lock:
                self._runners.pop(thread_id, None)

    def _run_payload_with_retries(self, payload: _TurnPayload) -> None:
        thread_id = payload["thread_id"]
        user_id = payload["user_id"]
        user_context = payload["user_context"]
        conversation_window = payload["conversation_window"]
        event_loop = payload["event_loop"]
        store = payload["store"]

        try:
            from app.agents.supervisor.memory.cold_path import run_episodic_memory_job, run_semantic_memory_job

            for attempt in range(COLD_PATH_MAX_RETRIES):
                try:
                    run_semantic_memory_job(
                        user_id=user_id,
                        thread_id=thread_id,
                        user_context=user_context,
                        conversation_window=conversation_window,
                        event_loop=event_loop,
                        store=store,
                    )

                    run_episodic_memory_job(
                        user_id=user_id,
                        thread_id=thread_id,
                        user_context=user_context,
                        conversation_window=conversation_window,
                        event_loop=event_loop,
                        store=store,
                    )

                    logger.debug(
                        "memory.cold_path.completed: thread_id=%s user_id=%s attempt=%d",
                        thread_id,
                        user_id,
                        attempt + 1,
                    )
                    return
                except Exception as e:
                    if attempt < COLD_PATH_MAX_RETRIES - 1:
                        backoff = COLD_PATH_RETRY_BACKOFF_SECONDS * (2**attempt)
                        logger.warning(
                            "memory.cold_path.retry: thread_id=%s user_id=%s attempt=%d error=%s backoff=%.1fs",
                            thread_id,
                            user_id,
                            attempt + 1,
                            str(e),
                            backoff,
                        )
                        time.sleep(backoff)
                    else:
                        logger.error(
                            "memory.cold_path.failed: thread_id=%s user_id=%s attempts=%d error=%s",
                            thread_id,
                            user_id,
                            COLD_PATH_MAX_RETRIES,
                            str(e),
                            exc_info=True,
                        )
                        return
        except Exception as e:
            logger.error(
                "memory.cold_path.job.error: thread_id=%s user_id=%s error=%s",
                thread_id,
                user_id,
                str(e),
                exc_info=True,
            )

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the threadpool executor.

        Args:
            wait: If True, wait for running jobs to complete.

        """
        self._executor.shutdown(wait=wait)
        logger.debug("memory.cold_path.shutdown: wait=%s", wait)


_memory_cold_path_manager: Optional[MemoryColdPathManager] = None
_manager_lock = threading.Lock()


def get_memory_cold_path_manager() -> MemoryColdPathManager:
    """Get or create the singleton MemoryColdPathManager instance."""
    global _memory_cold_path_manager
    with _manager_lock:
        if _memory_cold_path_manager is None:
            _memory_cold_path_manager = MemoryColdPathManager()
        return _memory_cold_path_manager

