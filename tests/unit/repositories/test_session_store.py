"""Tests for InMemorySessionStore."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app.repositories.session_store import InMemorySessionStore, get_session_store


class TestInMemorySessionStoreInitialization:
    """Test InMemorySessionStore initialization."""

    def test_store_initialization_with_defaults(self):
        """Test that store initializes with default values."""
        store = InMemorySessionStore()

        assert store.sessions == {}
        assert store.locks == {}
        assert store.user_threads == {}
        assert store.ttl == timedelta(hours=24*30)
        assert store.cleanup_interval == timedelta(minutes=60)
        assert store.cleanup_task is None

    def test_store_initialization_with_custom_ttl(self):
        """Test that store can be initialized with custom TTL."""
        store = InMemorySessionStore(ttl_hours=48, cleanup_interval_minutes=30)

        assert store.ttl == timedelta(hours=48)
        assert store.cleanup_interval == timedelta(minutes=30)

    def test_get_session_store_returns_global_instance(self):
        """Test that get_session_store returns the global instance."""
        global_store = get_session_store()

        assert isinstance(global_store, InMemorySessionStore)


class TestSessionStoreStartStop:
    """Test start and stop methods."""

    @pytest.mark.asyncio
    async def test_start_creates_cleanup_task(self):
        """Test that start creates the periodic cleanup task."""
        store = InMemorySessionStore()

        assert store.cleanup_task is None

        await store.start()

        assert store.cleanup_task is not None
        assert isinstance(store.cleanup_task, asyncio.Task)

        await store.stop()

    @pytest.mark.asyncio
    async def test_start_does_not_create_duplicate_task(self):
        """Test that calling start multiple times doesn't create duplicate tasks."""
        store = InMemorySessionStore()

        await store.start()
        first_task = store.cleanup_task

        await store.start()
        second_task = store.cleanup_task

        assert first_task is second_task

        await store.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_cleanup_task(self):
        """Test that stop cancels the cleanup task."""
        store = InMemorySessionStore()

        await store.start()
        assert store.cleanup_task is not None

        await store.stop()

        assert store.cleanup_task is None

    @pytest.mark.asyncio
    async def test_stop_without_task_does_nothing(self):
        """Test that stop without a running task doesn't raise error."""
        store = InMemorySessionStore()
        await store.stop()


class TestSetSession:
    """Test set_session method."""

    @pytest.mark.asyncio
    async def test_set_session_stores_context(self):
        """Test that set_session stores the session context."""
        store = InMemorySessionStore()
        session_id = "test-session-1"
        context = {"user_id": "user-123", "data": "test"}

        await store.set_session(session_id, context)

        assert session_id in store.sessions
        assert store.sessions[session_id]["user_id"] == "user-123"
        assert store.sessions[session_id]["data"] == "test"
        assert "last_accessed" in store.sessions[session_id]

    @pytest.mark.asyncio
    async def test_set_session_creates_lock(self):
        """Test that set_session creates a lock for the session."""
        store = InMemorySessionStore()
        session_id = "test-session-2"
        context = {"user_id": "user-123"}

        await store.set_session(session_id, context)

        assert session_id in store.locks
        assert isinstance(store.locks[session_id], asyncio.Lock)

    @pytest.mark.asyncio
    async def test_set_session_updates_user_threads_mapping(self):
        """Test that set_session updates user_threads mapping."""
        store = InMemorySessionStore()
        session_id = "test-session-3"
        user_id = "user-456"
        context = {"user_id": user_id}

        await store.set_session(session_id, context)

        assert user_id in store.user_threads
        assert session_id in store.user_threads[user_id]

    @pytest.mark.asyncio
    async def test_set_session_multiple_sessions_same_user(self):
        """Test that multiple sessions for same user are tracked."""
        store = InMemorySessionStore()
        user_id = "user-789"
        session1 = "session-1"
        session2 = "session-2"

        await store.set_session(session1, {"user_id": user_id})
        await store.set_session(session2, {"user_id": user_id})

        assert len(store.user_threads[user_id]) == 2
        assert session1 in store.user_threads[user_id]
        assert session2 in store.user_threads[user_id]

    @pytest.mark.asyncio
    async def test_set_session_updates_last_accessed(self):
        """Test that set_session updates last_accessed timestamp."""
        store = InMemorySessionStore()
        session_id = "test-session-4"
        context = {"user_id": "user-123"}

        before_time = datetime.now()
        await store.set_session(session_id, context)
        after_time = datetime.now()

        last_accessed = store.sessions[session_id]["last_accessed"]
        assert before_time <= last_accessed <= after_time


class TestGetSession:
    """Test get_session method."""

    @pytest.mark.asyncio
    async def test_get_session_returns_existing_session(self):
        """Test that get_session returns an existing session."""
        store = InMemorySessionStore()
        session_id = "test-session-5"
        context = {"user_id": "user-123", "data": "test"}

        await store.set_session(session_id, context)
        result = await store.get_session(session_id)

        assert result is not None
        assert result["user_id"] == "user-123"
        assert result["data"] == "test"

    @pytest.mark.asyncio
    async def test_get_session_returns_none_for_nonexistent(self):
        """Test that get_session returns None for non-existent session."""
        store = InMemorySessionStore()

        result = await store.get_session("nonexistent-session")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_session_updates_last_accessed(self):
        """Test that get_session updates last_accessed timestamp."""
        store = InMemorySessionStore()
        session_id = "test-session-6"
        context = {"user_id": "user-123"}

        first_time = datetime(2024, 1, 1, 12, 0, 0)
        second_time = datetime(2024, 1, 1, 12, 0, 1)

        with patch('app.repositories.session_store.datetime') as mock_datetime:
            mock_datetime.now.return_value = first_time
            await store.set_session(session_id, context)
            first_accessed = store.sessions[session_id]["last_accessed"]

            mock_datetime.now.return_value = second_time
            await store.get_session(session_id)
            second_accessed = store.sessions[session_id]["last_accessed"]

        assert second_accessed > first_accessed
        assert first_accessed == first_time
        assert second_accessed == second_time

    @pytest.mark.asyncio
    async def test_get_session_removes_expired_session(self):
        """Test that get_session removes expired sessions."""
        store = InMemorySessionStore(ttl_hours=1)
        session_id = "test-session-7"
        context = {"user_id": "user-123"}

        await store.set_session(session_id, context)

        store.sessions[session_id]["last_accessed"] = datetime.now() - timedelta(hours=2)

        result = await store.get_session(session_id)

        assert result is None
        assert session_id not in store.sessions
        assert session_id not in store.locks


class TestGetUserThreads:
    """Test get_user_threads method."""

    @pytest.mark.asyncio
    async def test_get_user_threads_returns_thread_ids(self):
        """Test that get_user_threads returns list of thread IDs for user."""
        store = InMemorySessionStore()
        user_id = "user-101"
        session1 = "thread-1"
        session2 = "thread-2"

        await store.set_session(session1, {"user_id": user_id})
        await store.set_session(session2, {"user_id": user_id})

        threads = await store.get_user_threads(user_id)

        assert len(threads) == 2
        assert session1 in threads
        assert session2 in threads

    @pytest.mark.asyncio
    async def test_get_user_threads_returns_empty_for_unknown_user(self):
        """Test that get_user_threads returns empty list for unknown user."""
        store = InMemorySessionStore()

        threads = await store.get_user_threads("unknown-user")

        assert threads == []


class TestUpdateSessionAccess:
    """Test update_session_access method."""

    @pytest.mark.asyncio
    async def test_update_session_access_updates_timestamp(self):
        """Test that update_session_access updates the timestamp."""
        store = InMemorySessionStore()
        session_id = "test-session-8"
        context = {"user_id": "user-123"}

        first_time = datetime(2024, 1, 1, 12, 0, 0)
        second_time = datetime(2024, 1, 1, 12, 0, 5)

        with patch('app.repositories.session_store.datetime') as mock_datetime:
            mock_datetime.now.return_value = first_time
            await store.set_session(session_id, context)
            first_accessed = store.sessions[session_id]["last_accessed"]

            mock_datetime.now.return_value = second_time
            await store.update_session_access(session_id)
            second_accessed = store.sessions[session_id]["last_accessed"]

        assert second_accessed > first_accessed
        assert first_accessed == first_time
        assert second_accessed == second_time

    @pytest.mark.asyncio
    async def test_update_session_access_does_nothing_for_nonexistent(self):
        """Test that update_session_access doesn't fail for non-existent session."""
        store = InMemorySessionStore()

        await store.update_session_access("nonexistent-session")


class TestCleanupExpired:
    """Test cleanup_expired method."""

    @pytest.mark.asyncio
    async def test_cleanup_expired_removes_old_sessions(self):
        """Test that cleanup_expired removes expired sessions."""
        store = InMemorySessionStore(ttl_hours=1)
        session1 = "active-session"
        session2 = "expired-session"

        await store.set_session(session1, {"user_id": "user-1"})
        await store.set_session(session2, {"user_id": "user-2"})

        store.sessions[session2]["last_accessed"] = datetime.now() - timedelta(hours=2)

        await store.cleanup_expired()

        assert session1 in store.sessions
        assert session2 not in store.sessions
        assert session2 not in store.locks

    @pytest.mark.asyncio
    async def test_cleanup_expired_removes_from_user_threads(self):
        """Test that cleanup_expired removes sessions from user_threads mapping."""
        store = InMemorySessionStore(ttl_hours=1)
        user_id = "user-cleanup"
        session1 = "keep-session"
        session2 = "remove-session"

        await store.set_session(session1, {"user_id": user_id})
        await store.set_session(session2, {"user_id": user_id})

        store.sessions[session2]["last_accessed"] = datetime.now() - timedelta(hours=2)

        await store.cleanup_expired()

        threads = await store.get_user_threads(user_id)
        assert session1 in threads
        assert session2 not in threads

    @pytest.mark.asyncio
    async def test_cleanup_expired_removes_empty_user_entries(self):
        """Test that cleanup_expired removes users with no sessions."""
        store = InMemorySessionStore(ttl_hours=1)
        user_id = "user-no-sessions"
        session_id = "only-session"

        await store.set_session(session_id, {"user_id": user_id})

        # Make session expired
        store.sessions[session_id]["last_accessed"] = datetime.now() - timedelta(hours=2)

        await store.cleanup_expired()

        assert user_id not in store.user_threads


class TestCleanupUserThreadMapping:
    """Test _cleanup_user_thread_mapping method."""

    def test_cleanup_user_thread_mapping_removes_session(self):
        """Test that _cleanup_user_thread_mapping removes session from mapping."""
        store = InMemorySessionStore()
        user_id = "user-mapping"
        session1 = "session-1"
        session2 = "session-2"

        # Manually set up user_threads
        store.user_threads[user_id] = {session1, session2}

        store._cleanup_user_thread_mapping(session1)

        assert session1 not in store.user_threads[user_id]
        assert session2 in store.user_threads[user_id]

    def test_cleanup_user_thread_mapping_removes_empty_users(self):
        """Test that _cleanup_user_thread_mapping removes empty user entries."""
        store = InMemorySessionStore()
        user_id = "user-cleanup-empty"
        session_id = "only-session"

        store.user_threads[user_id] = {session_id}

        store._cleanup_user_thread_mapping(session_id)

        assert user_id not in store.user_threads


class TestPeriodicCleanup:
    """Test _periodic_cleanup method."""

    @pytest.mark.asyncio
    async def test_periodic_cleanup_runs_cleanup(self):
        """Test that _periodic_cleanup task can be started and stopped."""
        store = InMemorySessionStore(cleanup_interval_minutes=1)

        await store.start()
        assert store.cleanup_task is not None

        await store.stop()
        assert store.cleanup_task is None

    @pytest.mark.asyncio
    async def test_periodic_cleanup_handles_cancellation(self):
        """Test that _periodic_cleanup handles cancellation gracefully."""
        store = InMemorySessionStore(cleanup_interval_minutes=1)

        await store.start()
        assert store.cleanup_task is not None

        await store.stop()
        assert store.cleanup_task is None
