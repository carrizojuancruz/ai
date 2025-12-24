from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.core.config import config as app_config
from app.models.user import UserContext

logger = logging.getLogger(__name__)

DEFAULT_CACHE_TTL_SECONDS: int = 60

CLEANUP_INTERVAL_SECONDS: int = 300


@dataclass
class CachedUserContextEntry:
    context: UserContext
    context_dict: dict[str, Any]
    content_hash: str
    fetched_at: float


class UserContextCache:
    """In-memory cache for user context with TTL and hash-based change detection.

    Features:
    - Per-user caching with configurable TTL
    - Content hash for detecting actual changes
    - Thread-safe async operations with per-user locks
    - Automatic cleanup of expired entries
    """

    def __init__(self, ttl_seconds: int | None = None) -> None:
        self._cache: dict[str, CachedUserContextEntry] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None

        config_ttl = getattr(app_config, "USER_CONTEXT_CACHE_TTL_SECONDS", None)
        self._ttl_seconds = ttl_seconds or config_ttl or DEFAULT_CACHE_TTL_SECONDS

        logger.info(
            "user_context_cache.init ttl_seconds=%d",
            self._ttl_seconds,
        )

    async def start(self) -> None:
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
            logger.info("user_context_cache.cleanup_task.started")

    async def stop(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task
            self._cleanup_task = None
            logger.info("user_context_cache.cleanup_task.stopped")

    async def _periodic_cleanup(self) -> None:
        while True:
            try:
                await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
                cleaned = await self._cleanup_expired()
                if cleaned > 0:
                    logger.info("user_context_cache.cleanup count=%d", cleaned)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("user_context_cache.cleanup.error err=%s", e)

    async def _cleanup_expired(self) -> int:
        now = time.time()
        expired_keys: list[str] = []

        async with self._global_lock:
            for key, entry in self._cache.items():
                if (now - entry.fetched_at) > self._ttl_seconds:
                    expired_keys.append(key)

            for key in expired_keys:
                self._cache.pop(key, None)
        return len(expired_keys)

    async def _get_lock(self, user_id: str) -> asyncio.Lock:
        if user_id not in self._locks:
            async with self._global_lock:
                if user_id not in self._locks:
                    self._locks[user_id] = asyncio.Lock()
        return self._locks[user_id]

    HASH_EXCLUDE_FIELDS: frozenset[str] = frozenset(
        {
            "created_at",
            "updated_at",
        }
    )

    @classmethod
    def _strip_volatile_fields(cls, data: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in data.items():
            if key in cls.HASH_EXCLUDE_FIELDS:
                continue
            if isinstance(value, dict):
                result[key] = cls._strip_volatile_fields(value)
            elif isinstance(value, list):
                result[key] = [cls._strip_volatile_fields(item) if isinstance(item, dict) else item for item in value]
            else:
                result[key] = value
        return result

    @classmethod
    def compute_hash(cls, context: UserContext | dict[str, Any]) -> str:
        context_dict = context.model_dump(mode="json") if isinstance(context, UserContext) else context

        stable_dict = cls._strip_volatile_fields(context_dict)

        serialized = json.dumps(stable_dict, sort_keys=True, default=str)
        return hashlib.md5(serialized.encode(), usedforsecurity=False).hexdigest()

    def _is_expired(self, entry: CachedUserContextEntry) -> bool:
        return (time.time() - entry.fetched_at) > self._ttl_seconds

    def get_cached(self, user_id: UUID | str) -> CachedUserContextEntry | None:
        cache_key = str(user_id)
        entry = self._cache.get(cache_key)

        if entry is None:
            return None

        if self._is_expired(entry):
            self._cache.pop(cache_key, None)
            return None

        return entry

    async def get_or_fetch(
        self,
        user_id: UUID,
        fetch_fn,
        force_refresh: bool = False,
    ) -> tuple[UserContext, dict[str, Any], str, bool]:
        cache_key = str(user_id)
        lock = await self._get_lock(cache_key)

        async with lock:
            if not force_refresh:
                entry = self.get_cached(user_id)
                if entry is not None:
                    logger.info(
                        "user_context_cache.hit user_id=%s age_seconds=%.1f",
                        user_id,
                        time.time() - entry.fetched_at,
                    )
                    return entry.context, entry.context_dict, entry.content_hash, False

            t0 = time.perf_counter()
            try:
                context = await fetch_fn(user_id)
            except Exception as e:
                logger.error(
                    "user_context_cache.fetch.error user_id=%s err=%s",
                    user_id,
                    e,
                )
                stale_entry = self._cache.get(cache_key)
                if stale_entry is not None:
                    logger.warning(
                        "user_context_cache.fetch.fallback_to_stale user_id=%s",
                        user_id,
                    )
                    return stale_entry.context, stale_entry.context_dict, stale_entry.content_hash, False
                raise

            t1 = time.perf_counter()
            fetch_ms = int((t1 - t0) * 1000)

            context_dict = context.model_dump(mode="json")
            new_hash = self.compute_hash(context_dict)

            old_entry = self._cache.get(cache_key)
            content_changed = old_entry is None or old_entry.content_hash != new_hash

            new_entry = CachedUserContextEntry(
                context=context,
                context_dict=context_dict,
                content_hash=new_hash,
                fetched_at=time.time(),
            )
            self._cache[cache_key] = new_entry

            log_level = "miss" if old_entry is None else ("refresh" if force_refresh else "expired")
            logger.info(
                "user_context_cache.%s user_id=%s fetch_ms=%d content_changed=%s",
                log_level,
                user_id,
                fetch_ms,
                content_changed,
            )

            return context, context_dict, new_hash, content_changed

    def invalidate(self, user_id: UUID | str) -> bool:
        cache_key = str(user_id)
        entry = self._cache.pop(cache_key, None)
        if entry is not None:
            logger.info("user_context_cache.invalidate user_id=%s", user_id)
            return True
        return False

    def invalidate_all(self) -> int:
        count = len(self._cache)
        self._cache.clear()
        self._locks.clear()
        logger.info("user_context_cache.invalidate_all count=%d", count)
        return count

    def get_stats(self) -> dict[str, Any]:
        now = time.time()
        entries = list(self._cache.values())
        ages = [now - e.fetched_at for e in entries]

        return {
            "total_entries": len(entries),
            "ttl_seconds": self._ttl_seconds,
            "avg_age_seconds": sum(ages) / len(ages) if ages else 0,
            "oldest_age_seconds": max(ages) if ages else 0,
            "newest_age_seconds": min(ages) if ages else 0,
        }


_user_context_cache: UserContextCache | None = None


def get_user_context_cache() -> UserContextCache:
    global _user_context_cache
    if _user_context_cache is None:
        _user_context_cache = UserContextCache()
    return _user_context_cache


async def start_user_context_cache() -> None:
    cache = get_user_context_cache()
    await cache.start()


async def stop_user_context_cache() -> None:
    if _user_context_cache is not None:
        await _user_context_cache.stop()
