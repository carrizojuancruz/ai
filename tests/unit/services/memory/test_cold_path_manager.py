"""
Unit tests for app.services.memory.cold_path_manager module.

Tests cover:
- MemoryColdPathManager initialization
- Job submission and coalescing (latest payload wins)
- Per-thread serialization (runner loop)
- Retry logic with backoff
- Error handling
- Shutdown behavior
"""

import threading
from unittest.mock import MagicMock, patch

from app.services.memory.cold_path_manager import MemoryColdPathManager, get_memory_cold_path_manager


class TestMemoryColdPathManager:
    """Test MemoryColdPathManager class."""

    def test_init_default_workers(self):
        """Test initialization with default worker count."""
        manager = MemoryColdPathManager()
        assert manager._executor is not None
        assert len(manager._runners) == 0
        assert len(manager._latest_payload) == 0
        assert len(manager._locks) == 0
        manager.shutdown()

    def test_init_custom_workers(self):
        """Test initialization with custom worker count."""
        manager = MemoryColdPathManager(max_workers=8)
        assert manager._executor._max_workers == 8
        manager.shutdown()

    def test_get_thread_lock_creates_new(self):
        """Test that _get_thread_lock creates new locks."""
        manager = MemoryColdPathManager()
        thread_id = "thread-123"

        lock1 = manager._get_thread_lock(thread_id)
        lock2 = manager._get_thread_lock(thread_id)

        assert lock1 is lock2
        assert thread_id in manager._locks
        manager.shutdown()

    def test_get_thread_lock_different_threads(self):
        """Test that different thread_ids get different locks."""
        manager = MemoryColdPathManager()
        thread_id1 = "thread-123"
        thread_id2 = "thread-456"

        lock1 = manager._get_thread_lock(thread_id1)
        lock2 = manager._get_thread_lock(thread_id2)

        assert lock1 is not lock2
        assert thread_id1 in manager._locks
        assert thread_id2 in manager._locks
        manager.shutdown()

    def test_submit_turn_missing_thread_id(self):
        """Test submit_turn skips when thread_id is missing."""
        manager = MemoryColdPathManager()

        with patch("app.services.memory.cold_path_manager.logger") as mock_logger:
            manager.submit_turn(
                thread_id="",
                user_id="user-123",
                user_context={},
                conversation_window=[],
                store=MagicMock(),
            )

            mock_logger.warning.assert_called_once()
            assert "thread_id missing" in str(mock_logger.warning.call_args).lower()
        manager.shutdown()

    def test_submit_turn_no_event_loop(self):
        """Test submit_turn handles missing event loop."""
        manager = MemoryColdPathManager()

        with patch("app.services.memory.cold_path_manager.asyncio.get_running_loop") as mock_get_loop, \
             patch("app.services.memory.cold_path_manager.logger") as mock_logger:
            mock_get_loop.side_effect = RuntimeError("No event loop")

            manager.submit_turn(
                thread_id="thread-123",
                user_id="user-123",
                user_context={},
                conversation_window=[],
                store=MagicMock(),
            )

            mock_logger.warning.assert_called_once()
            assert "no event loop" in str(mock_logger.warning.call_args).lower()
        manager.shutdown()

    def test_submit_turn_success(self):
        """Test successful job submission starts a runner and stores latest payload."""
        manager = MemoryColdPathManager()
        thread_id = "thread-123"
        user_id = "user-123"
        user_context = {"name": "John"}
        conversation_window = [{"role": "user", "content": "Hello"}]

        mock_event_loop = MagicMock()

        with patch.object(manager._executor, "submit") as mock_submit:
            mock_runner_future = MagicMock()
            mock_runner_future.done.return_value = False
            mock_submit.return_value = mock_runner_future

            manager.submit_turn(
                thread_id=thread_id,
                user_id=user_id,
                user_context=user_context,
                conversation_window=conversation_window,
                store=MagicMock(),
                event_loop=mock_event_loop,
            )

            assert thread_id in manager._latest_payload
            assert thread_id in manager._runners
            mock_submit.assert_called_once()
        manager.shutdown(wait=False)

    def test_submit_turn_coalesces_latest_payload(self):
        """Test that multiple submits keep only latest payload (latest wins)."""
        manager = MemoryColdPathManager()
        thread_id = "thread-123"
        mock_event_loop = MagicMock()

        with patch.object(manager._executor, "submit") as mock_submit:
            mock_runner_future = MagicMock()
            mock_runner_future.done.return_value = False
            mock_submit.return_value = mock_runner_future

            manager.submit_turn(
                thread_id=thread_id,
                user_id="user-123",
                user_context={"v": 1},
                conversation_window=[{"role": "user", "content": "first"}],
                store=MagicMock(),
                event_loop=mock_event_loop,
            )
            manager.submit_turn(
                thread_id=thread_id,
                user_id="user-123",
                user_context={"v": 2},
                conversation_window=[{"role": "user", "content": "second"}],
                store=MagicMock(),
                event_loop=mock_event_loop,
            )

            assert manager._latest_payload[thread_id]["user_context"]["v"] == 2
            # Runner started once; second submit should not start another runner while first is active.
            mock_submit.assert_called_once()
        manager.shutdown(wait=False)

    def test_run_payload_with_retries_success(self):
        """Test successful payload execution (semantic then episodic)."""
        manager = MemoryColdPathManager()
        payload = {
            "thread_id": "thread-123",
            "user_id": "user-123",
            "user_context": {},
            "conversation_window": [{"role": "user", "content": "Hello"}],
            "event_loop": MagicMock(),
            "store": MagicMock(),
        }

        with patch("app.agents.supervisor.memory.cold_path.run_semantic_memory_job") as mock_semantic, \
             patch("app.agents.supervisor.memory.cold_path.run_episodic_memory_job") as mock_episodic, \
             patch("app.services.memory.cold_path_manager.logger") as mock_logger:
            manager._run_payload_with_retries(payload)
            mock_semantic.assert_called_once()
            mock_episodic.assert_called_once()
            mock_logger.debug.assert_called()
        manager.shutdown()

    def test_run_payload_with_retries_retry_on_failure(self):
        """Test retry logic on transient failures."""
        manager = MemoryColdPathManager()
        payload = {
            "thread_id": "thread-123",
            "user_id": "user-123",
            "user_context": {},
            "conversation_window": [],
            "event_loop": MagicMock(),
            "store": MagicMock(),
        }

        with patch("app.agents.supervisor.memory.cold_path.run_semantic_memory_job") as mock_semantic, \
             patch("app.agents.supervisor.memory.cold_path.run_episodic_memory_job") as mock_episodic, \
             patch("app.services.memory.cold_path_manager.logger") as mock_logger, \
             patch("time.sleep") as mock_sleep, \
             patch("app.services.memory.cold_path_manager.COLD_PATH_MAX_RETRIES", 3):
            mock_semantic.side_effect = [Exception("Transient"), Exception("Transient"), None]
            mock_episodic.return_value = None
            manager._run_payload_with_retries(payload)
            assert mock_semantic.call_count == 3
            assert mock_sleep.call_count == 2
            mock_logger.warning.assert_called()
            mock_logger.debug.assert_called()
        manager.shutdown()

    def test_run_payload_with_retries_max_retries_exceeded(self):
        """Test final failure after max retries."""
        manager = MemoryColdPathManager()
        payload = {
            "thread_id": "thread-123",
            "user_id": "user-123",
            "user_context": {},
            "conversation_window": [],
            "event_loop": MagicMock(),
            "store": MagicMock(),
        }

        with patch("app.agents.supervisor.memory.cold_path.run_semantic_memory_job") as mock_semantic, \
             patch("app.services.memory.cold_path_manager.logger") as mock_logger, \
             patch("time.sleep") as mock_sleep, \
             patch("app.services.memory.cold_path_manager.COLD_PATH_MAX_RETRIES", 2):
            mock_semantic.side_effect = Exception("Persistent")
            manager._run_payload_with_retries(payload)
            assert mock_semantic.call_count == 2
            assert mock_sleep.call_count == 1
            mock_logger.error.assert_called()
        manager.shutdown()

    def test_cleanup_stale_thread_state_removes_idle_threads(self):
        """Test TTL cleanup removes thread state when idle and expired."""
        manager = MemoryColdPathManager()
        thread_id = "thread-123"
        lock = manager._get_thread_lock(thread_id)
        assert lock is not None

        with manager._lock:
            manager._last_seen_at[thread_id] = 0.0
            manager._latest_payload.pop(thread_id, None)
            manager._runners.pop(thread_id, None)
            manager._cleanup_stale_thread_state(now=999999.0)

        assert thread_id not in manager._locks
        assert thread_id not in manager._last_seen_at
        manager.shutdown()

    def test_shutdown_wait_true(self):
        """Test shutdown with wait=True."""
        manager = MemoryColdPathManager()

        manager.shutdown(wait=True)

        assert manager._executor._shutdown

    def test_shutdown_wait_false(self):
        """Test shutdown with wait=False."""
        manager = MemoryColdPathManager()

        manager.shutdown(wait=False)

        assert manager._executor._shutdown


class TestGetMemoryColdPathManager:
    """Test get_memory_cold_path_manager singleton function."""

    def test_get_memory_cold_path_manager_singleton(self):
        """Test that get_memory_cold_path_manager returns singleton."""
        # Clear the singleton
        import app.services.memory.cold_path_manager as manager_module
        manager_module._memory_cold_path_manager = None

        manager1 = get_memory_cold_path_manager()
        manager2 = get_memory_cold_path_manager()

        assert manager1 is manager2
        assert isinstance(manager1, MemoryColdPathManager)

        manager1.shutdown()

    def test_get_memory_cold_path_manager_thread_safe(self):
        """Test that singleton creation is thread-safe."""
        import app.services.memory.cold_path_manager as manager_module
        manager_module._memory_cold_path_manager = None

        managers = []
        lock = threading.Lock()

        def get_manager():
            manager = get_memory_cold_path_manager()
            with lock:
                managers.append(manager)

        threads = [threading.Thread(target=get_manager) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should be the same instance
        assert all(m is managers[0] for m in managers)
        managers[0].shutdown()

