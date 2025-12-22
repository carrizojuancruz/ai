import asyncio
import time
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.models.user import UserContext
from app.services.user_context_cache import (
    DEFAULT_CACHE_TTL_SECONDS,
    CachedUserContextEntry,
    UserContextCache,
    get_user_context_cache,
    start_user_context_cache,
    stop_user_context_cache,
)


@pytest.fixture
def cache():
    return UserContextCache(ttl_seconds=60)


@pytest.fixture
def mock_user_id():
    return UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def mock_user_context():
    return MagicMock(
        spec=UserContext,
        user_id=UUID("12345678-1234-5678-1234-567812345678"),
        preferred_name="TestUser",
        city="New York",
    )


@pytest.fixture
def mock_context_dict():
    return {
        "user_id": "12345678-1234-5678-1234-567812345678",
        "preferred_name": "TestUser",
        "city": "New York",
        "created_at": "2025-01-01T00:00:00",
        "updated_at": "2025-01-01T00:00:00",
    }


class TestUserContextCacheInit:
    def test_default_ttl(self):
        cache = UserContextCache()
        assert cache._ttl_seconds == DEFAULT_CACHE_TTL_SECONDS

    def test_custom_ttl(self):
        cache = UserContextCache(ttl_seconds=120)
        assert cache._ttl_seconds == 120

    def test_initial_state(self, cache):
        assert len(cache._cache) == 0
        assert len(cache._locks) == 0
        assert cache._cleanup_task is None


class TestVolatileFieldStripping:
    def test_strips_created_at(self):
        data = {"name": "Test", "created_at": "2025-01-01T00:00:00"}
        result = UserContextCache._strip_volatile_fields(data)
        assert "created_at" not in result
        assert result["name"] == "Test"

    def test_strips_updated_at(self):
        data = {"name": "Test", "updated_at": "2025-01-01T00:00:00"}
        result = UserContextCache._strip_volatile_fields(data)
        assert "updated_at" not in result
        assert result["name"] == "Test"

    def test_strips_nested_volatile_fields(self):
        data = {
            "name": "Test",
            "nested": {
                "value": 123,
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:00",
            },
        }
        result = UserContextCache._strip_volatile_fields(data)
        assert "created_at" not in result["nested"]
        assert "updated_at" not in result["nested"]
        assert result["nested"]["value"] == 123

    def test_strips_volatile_fields_in_lists(self):
        data = {
            "items": [
                {"id": 1, "created_at": "2025-01-01"},
                {"id": 2, "updated_at": "2025-01-02"},
            ]
        }
        result = UserContextCache._strip_volatile_fields(data)
        assert "created_at" not in result["items"][0]
        assert "updated_at" not in result["items"][1]
        assert result["items"][0]["id"] == 1
        assert result["items"][1]["id"] == 2

    def test_preserves_non_volatile_fields(self):
        data = {
            "name": "Test",
            "age": 25,
            "city": "NYC",
            "created_at": "2025-01-01",
        }
        result = UserContextCache._strip_volatile_fields(data)
        assert result["name"] == "Test"
        assert result["age"] == 25
        assert result["city"] == "NYC"


class TestHashComputation:
    def test_same_content_same_hash(self):
        data1 = {"name": "Test", "value": 123}
        data2 = {"name": "Test", "value": 123}
        assert UserContextCache.compute_hash(data1) == UserContextCache.compute_hash(data2)

    def test_different_content_different_hash(self):
        data1 = {"name": "Test1", "value": 123}
        data2 = {"name": "Test2", "value": 123}
        assert UserContextCache.compute_hash(data1) != UserContextCache.compute_hash(data2)

    def test_volatile_fields_ignored_in_hash(self):
        data1 = {"name": "Test", "created_at": "2025-01-01T00:00:00"}
        data2 = {"name": "Test", "created_at": "2025-12-31T23:59:59"}
        assert UserContextCache.compute_hash(data1) == UserContextCache.compute_hash(data2)

    def test_hash_is_deterministic(self):
        data1 = {"b": 2, "a": 1}
        data2 = {"a": 1, "b": 2}
        assert UserContextCache.compute_hash(data1) == UserContextCache.compute_hash(data2)


class TestCacheOperations:
    @pytest.mark.asyncio
    async def test_cache_miss_on_empty_cache(self, cache, mock_user_id, mock_user_context):
        mock_fetch = AsyncMock(return_value=mock_user_context)
        mock_user_context.model_dump = MagicMock(return_value={"name": "Test"})

        ctx, ctx_dict, ctx_hash, changed = await cache.get_or_fetch(mock_user_id, mock_fetch)

        assert ctx == mock_user_context
        assert changed is True
        mock_fetch.assert_called_once_with(mock_user_id)

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_entry(self, cache, mock_user_id, mock_user_context):
        mock_fetch = AsyncMock(return_value=mock_user_context)
        mock_user_context.model_dump = MagicMock(return_value={"name": "Test"})

        await cache.get_or_fetch(mock_user_id, mock_fetch)

        ctx, ctx_dict, ctx_hash, changed = await cache.get_or_fetch(mock_user_id, mock_fetch)

        assert changed is False
        assert mock_fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_cache(self, cache, mock_user_id, mock_user_context):
        mock_fetch = AsyncMock(return_value=mock_user_context)
        mock_user_context.model_dump = MagicMock(return_value={"name": "Test"})

        await cache.get_or_fetch(mock_user_id, mock_fetch)

        await cache.get_or_fetch(mock_user_id, mock_fetch, force_refresh=True)

        assert mock_fetch.call_count == 2


class TestCacheExpiration:
    @pytest.mark.asyncio
    async def test_expired_entry_triggers_refetch(self, mock_user_id, mock_user_context):
        cache = UserContextCache(ttl_seconds=1)
        mock_fetch = AsyncMock(return_value=mock_user_context)
        mock_user_context.model_dump = MagicMock(return_value={"name": "Test"})

        await cache.get_or_fetch(mock_user_id, mock_fetch)

        await asyncio.sleep(1.1)

        await cache.get_or_fetch(mock_user_id, mock_fetch)

        assert mock_fetch.call_count == 2

    def test_is_expired_check(self, cache):
        entry = CachedUserContextEntry(
            context=MagicMock(),
            context_dict={},
            content_hash="abc",
            fetched_at=time.time() - 120,
        )

        assert cache._is_expired(entry) is True

    def test_not_expired_check(self, cache):
        entry = CachedUserContextEntry(
            context=MagicMock(),
            context_dict={},
            content_hash="abc",
            fetched_at=time.time(),
        )

        assert cache._is_expired(entry) is False


class TestCacheInvalidation:
    @pytest.mark.asyncio
    async def test_invalidate_removes_entry(self, cache, mock_user_id, mock_user_context):
        mock_fetch = AsyncMock(return_value=mock_user_context)
        mock_user_context.model_dump = MagicMock(return_value={"name": "Test"})

        await cache.get_or_fetch(mock_user_id, mock_fetch)
        assert len(cache._cache) == 1

        result = cache.invalidate(mock_user_id)

        assert result is True
        assert len(cache._cache) == 0

    @pytest.mark.asyncio
    async def test_invalidate_removes_lock(self, cache, mock_user_id, mock_user_context):
        mock_fetch = AsyncMock(return_value=mock_user_context)
        mock_user_context.model_dump = MagicMock(return_value={"name": "Test"})

        await cache.get_or_fetch(mock_user_id, mock_fetch)
        assert str(mock_user_id) in cache._locks

        cache.invalidate(mock_user_id)

        assert str(mock_user_id) not in cache._locks

    def test_invalidate_returns_false_if_not_found(self, cache, mock_user_id):
        result = cache.invalidate(mock_user_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_invalidate_all(self, cache, mock_user_context):
        mock_fetch = AsyncMock(return_value=mock_user_context)
        mock_user_context.model_dump = MagicMock(return_value={"name": "Test"})

        user1 = UUID("11111111-1111-1111-1111-111111111111")
        user2 = UUID("22222222-2222-2222-2222-222222222222")

        await cache.get_or_fetch(user1, mock_fetch)
        await cache.get_or_fetch(user2, mock_fetch)

        assert len(cache._cache) == 2
        assert len(cache._locks) == 2

        count = cache.invalidate_all()

        assert count == 2
        assert len(cache._cache) == 0
        assert len(cache._locks) == 0


class TestCacheCleanup:
    @pytest.mark.asyncio
    async def test_cleanup_removes_expired_entries(self, mock_user_context):
        cache = UserContextCache(ttl_seconds=1)
        mock_fetch = AsyncMock(return_value=mock_user_context)
        mock_user_context.model_dump = MagicMock(return_value={"name": "Test"})

        user_id = UUID("12345678-1234-5678-1234-567812345678")
        await cache.get_or_fetch(user_id, mock_fetch)

        await asyncio.sleep(1.1)

        cleaned = await cache._cleanup_expired()

        assert cleaned == 1
        assert len(cache._cache) == 0
        assert len(cache._locks) == 0

    @pytest.mark.asyncio
    async def test_start_creates_cleanup_task(self, cache):
        assert cache._cleanup_task is None

        await cache.start()

        assert cache._cleanup_task is not None
        assert not cache._cleanup_task.done()

        await cache.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_cleanup_task(self, cache):
        await cache.start()
        task = cache._cleanup_task

        await cache.stop()

        assert cache._cleanup_task is None
        assert task.cancelled() or task.done()


class TestCacheStats:
    @pytest.mark.asyncio
    async def test_get_stats_empty_cache(self, cache):
        stats = cache.get_stats()

        assert stats["total_entries"] == 0
        assert stats["ttl_seconds"] == 60
        assert stats["avg_age_seconds"] == 0

    @pytest.mark.asyncio
    async def test_get_stats_with_entries(self, cache, mock_user_id, mock_user_context):
        mock_fetch = AsyncMock(return_value=mock_user_context)
        mock_user_context.model_dump = MagicMock(return_value={"name": "Test"})

        await cache.get_or_fetch(mock_user_id, mock_fetch)

        stats = cache.get_stats()

        assert stats["total_entries"] == 1
        assert stats["avg_age_seconds"] >= 0


class TestFetchErrorHandling:
    @pytest.mark.asyncio
    async def test_fetch_error_uses_stale_cache_on_force_refresh(self, cache, mock_user_id, mock_user_context):
        mock_fetch = AsyncMock(return_value=mock_user_context)
        mock_user_context.model_dump = MagicMock(return_value={"name": "Test"})

        await cache.get_or_fetch(mock_user_id, mock_fetch)

        mock_fetch.side_effect = Exception("Network error")

        ctx, _, _, changed = await cache.get_or_fetch(mock_user_id, mock_fetch, force_refresh=True)

        assert ctx == mock_user_context
        assert changed is False

    @pytest.mark.asyncio
    async def test_fetch_error_raises_if_no_stale_cache(self, cache, mock_user_id):
        mock_fetch = AsyncMock(side_effect=Exception("Network error"))

        with pytest.raises(Exception, match="Network error"):
            await cache.get_or_fetch(mock_user_id, mock_fetch)


class TestSingletonFunctions:
    def test_get_user_context_cache_returns_same_instance(self):
        import app.services.user_context_cache as module

        module._user_context_cache = None

        cache1 = get_user_context_cache()
        cache2 = get_user_context_cache()

        assert cache1 is cache2

    @pytest.mark.asyncio
    async def test_start_and_stop_functions(self):
        import app.services.user_context_cache as module

        module._user_context_cache = None

        await start_user_context_cache()
        cache = get_user_context_cache()

        assert cache._cleanup_task is not None

        await stop_user_context_cache()

        assert cache._cleanup_task is None
