from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


class InMemorySessionStore:
    def __init__(self, ttl_hours: int = 24, cleanup_interval_minutes: int = 30) -> None:
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.locks: Dict[str, asyncio.Lock] = {}
        self.ttl = timedelta(hours=ttl_hours)
        self.cleanup_interval = timedelta(minutes=cleanup_interval_minutes)
        self.cleanup_task: Optional[asyncio.Task] = None
        self._store_lock = asyncio.Lock()

    async def start(self) -> None:
        if self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def stop(self) -> None:
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
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

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        ctx = self.sessions.get(session_id)
        if ctx:
            if datetime.now() - ctx.get("last_accessed", datetime.now()) > self.ttl:
                self.sessions.pop(session_id, None)
                return None
            ctx["last_accessed"] = datetime.now()
            return ctx
        return None

    async def set_session(self, session_id: str, context: Dict[str, Any]) -> None:
        context["last_accessed"] = datetime.now()
        async with self._store_lock:
            self.sessions[session_id] = context
            if session_id not in self.locks:
                self.locks[session_id] = asyncio.Lock()

    async def update_session_access(self, session_id: str) -> None:
        if session_id in self.sessions:
            self.sessions[session_id]["last_accessed"] = datetime.now()


_session_store = InMemorySessionStore()


def get_session_store() -> InMemorySessionStore:
    return _session_store


