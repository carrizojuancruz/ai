from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timedelta
from typing import Any


class InMemorySessionStore:
    def __init__(self, ttl_hours: int = 24*30, cleanup_interval_minutes: int = 60) -> None:  # 30 days for dev
        self.sessions: dict[str, dict[str, Any]] = {}
        self.locks: dict[str, asyncio.Lock] = {}
        self.user_threads: dict[str, set[str]] = {}  # user_id -> set of thread_ids
        self.ttl = timedelta(hours=ttl_hours)
        self.cleanup_interval = timedelta(minutes=cleanup_interval_minutes)
        self.cleanup_task: asyncio.Task | None = None
        self._store_lock = asyncio.Lock()

    async def start(self) -> None:
        if self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def stop(self) -> None:
        if self.cleanup_task:
            self.cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.cleanup_task
            self.cleanup_task = None

    async def _periodic_cleanup(self) -> None:
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval.total_seconds())
                await self.cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception:
                # Best-effort cleanup; ignore errors
                pass

    async def cleanup_expired(self) -> None:
        now = datetime.now()
        expired = [
            sid
            for sid, ctx in self.sessions.items()
            if now - ctx.get("last_accessed", now) > self.ttl
        ]
        async with self._store_lock:
            for sid in expired:
                self.sessions.pop(sid, None)
                self.locks.pop(sid, None)
                self._cleanup_user_thread_mapping(sid)

    def _cleanup_user_thread_mapping(self, session_id: str) -> None:
        """Remove session from user_threads mapping when session expires."""
        for user_threads in self.user_threads.values():
            user_threads.discard(session_id)
        # Clean up empty user entries
        self.user_threads = {k: v for k, v in self.user_threads.items() if v}

    async def get_user_threads(self, user_id: str) -> list[str]:
        """Get all thread IDs for a user (O(1) lookup)."""
        return list(self.user_threads.get(user_id, set()))

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        ctx = self.sessions.get(session_id)
        if ctx:
            if datetime.now() - ctx.get("last_accessed", datetime.now()) > self.ttl:
                async with self._store_lock:
                    self.sessions.pop(session_id, None)
                    self.locks.pop(session_id, None)
                    self._cleanup_user_thread_mapping(session_id)
                return None
            ctx["last_accessed"] = datetime.now()
            return ctx
        return None

    async def set_session(self, session_id: str, context: dict[str, Any]) -> None:
        context["last_accessed"] = datetime.now()
        async with self._store_lock:
            self.sessions[session_id] = context
            if session_id not in self.locks:
                self.locks[session_id] = asyncio.Lock()

            # Maintain user_id -> thread_id mapping
            user_id = context.get("user_id")
            if user_id:
                if user_id not in self.user_threads:
                    self.user_threads[user_id] = set()
                self.user_threads[user_id].add(session_id)

    async def update_session_access(self, session_id: str) -> None:
        if session_id in self.sessions:
            self.sessions[session_id]["last_accessed"] = datetime.now()


_session_store = InMemorySessionStore()


def get_session_store() -> InMemorySessionStore:
    return _session_store


