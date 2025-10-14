"""Unit tests for app.core.app_state module."""

import asyncio
import contextlib
import time
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from app.core import app_state


class TestSingletonGetters:
    """Test singleton getter functions."""

    def test_agent_getters_create_singletons(self, reset_app_state_globals):
        """Test that agent getter functions create and return singleton instances."""
        with patch('app.agents.onboarding.OnboardingAgent') as mock_onboarding_class, \
             patch('app.agents.supervisor.compile_supervisor_graph') as mock_supervisor_compile, \
             patch('app.agents.supervisor.finance_agent.agent.FinanceAgent') as mock_finance_class, \
             patch('app.agents.supervisor.wealth_agent.agent.WealthAgent') as mock_wealth_class:

            mock_onboarding = Mock()
            mock_onboarding_class.return_value = mock_onboarding
            mock_supervisor = Mock()
            mock_supervisor_compile.return_value = mock_supervisor
            mock_finance = Mock()
            mock_finance_class.return_value = mock_finance
            mock_wealth = Mock()
            mock_wealth_class.return_value = mock_wealth

            onboarding1 = app_state.get_onboarding_agent()
            onboarding2 = app_state.get_onboarding_agent()
            supervisor1 = app_state.get_supervisor_graph()
            supervisor2 = app_state.get_supervisor_graph()
            finance1 = app_state.get_finance_agent()
            finance2 = app_state.get_finance_agent()
            wealth1 = app_state.get_wealth_agent()
            wealth2 = app_state.get_wealth_agent()

            assert onboarding1 == mock_onboarding and onboarding2 == mock_onboarding
            assert supervisor1 == mock_supervisor and supervisor2 == mock_supervisor
            assert finance1 == mock_finance and finance2 == mock_finance
            assert wealth1 == mock_wealth and wealth2 == mock_wealth
            mock_onboarding_class.assert_called_once()
            mock_supervisor_compile.assert_called_once()
            mock_finance_class.assert_called_once()
            mock_wealth_class.assert_called_once()

    def test_get_wealth_agent_graph(self, reset_app_state_globals):
        """Test get_wealth_agent_graph function."""
        with patch('app.agents.supervisor.wealth_agent.agent.compile_wealth_agent_graph') as mock_compile:
            mock_graph = Mock()
            mock_compile.return_value = mock_graph

            result = app_state.get_wealth_agent_graph()

            assert result == mock_graph
            mock_compile.assert_called_once()

    def test_get_goal_agent_graph(self, reset_app_state_globals):
        """Test get_goal_agent_graph function."""
        with patch('app.agents.supervisor.goal_agent.agent.compile_goal_agent_graph') as mock_compile:
            mock_graph = Mock()
            mock_compile.return_value = mock_graph

            result = app_state.get_goal_agent_graph()

            assert result == mock_graph
            mock_compile.assert_called_once()

    def test_get_goal_agent(self, reset_app_state_globals):
        """Test get_goal_agent function."""
        with patch('app.core.app_state.get_goal_agent') as mock_get_goal:
            mock_agent = Mock()
            mock_get_goal.return_value = mock_agent

            result = app_state.get_goal_agent()

            assert result == mock_agent


class TestThreadManagement:
    """Test thread state management functions."""

    def test_register_thread(self, reset_app_state_globals):
        """Test registering a new thread."""
        thread_id = "test-thread-123"
        mock_state = Mock()

        app_state.register_thread(thread_id, mock_state)

        assert thread_id in app_state._onboarding_threads
        assert app_state._onboarding_threads[thread_id] == mock_state

    def test_get_thread_state_existing(self, reset_app_state_globals):
        """Test getting state of existing thread."""
        thread_id = "test-thread-123"
        mock_state = Mock()
        app_state._onboarding_threads[thread_id] = mock_state

        result = app_state.get_thread_state(thread_id)

        assert result == mock_state

    def test_get_thread_state_nonexistent(self, reset_app_state_globals):
        """Test getting state of nonexistent thread returns None."""
        result = app_state.get_thread_state("nonexistent-thread")

        assert result is None

    def test_set_thread_state(self, reset_app_state_globals):
        """Test setting thread state."""
        thread_id = "test-thread-123"
        mock_state = Mock()

        app_state.set_thread_state(thread_id, mock_state)

        assert app_state._onboarding_threads[thread_id] == mock_state


class TestSSEQueueManagement:
    """Test SSE queue management functions."""

    def test_get_sse_queue_creates_new(self, reset_app_state_globals):
        """Test getting SSE queue creates new queue if not exists."""
        thread_id = "test-thread-123"

        queue = app_state.get_sse_queue(thread_id)

        assert isinstance(queue, asyncio.Queue)
        assert thread_id in app_state._sse_queues

    def test_get_sse_queue_returns_existing(self, reset_app_state_globals):
        """Test getting SSE queue returns existing queue."""
        thread_id = "test-thread-123"
        existing_queue = asyncio.Queue()
        app_state._sse_queues[thread_id] = existing_queue

        queue = app_state.get_sse_queue(thread_id)

        assert queue is existing_queue

    def test_drop_sse_queue(self, reset_app_state_globals):
        """Test dropping SSE queue."""
        thread_id = "test-thread-123"
        app_state._sse_queues[thread_id] = asyncio.Queue()

        app_state.drop_sse_queue(thread_id)

        assert thread_id not in app_state._sse_queues

    def test_drop_sse_queue_nonexistent(self, reset_app_state_globals):
        """Test dropping nonexistent queue doesn't raise error."""
        app_state.drop_sse_queue("nonexistent-thread")


class TestThreadLocks:
    """Test thread lock management."""

    def test_get_thread_lock_creates_new(self, reset_app_state_globals):
        """Test getting thread lock creates new lock if not exists."""
        thread_id = "test-thread-123"

        lock = app_state.get_thread_lock(thread_id)

        assert isinstance(lock, asyncio.Lock)
        assert thread_id in app_state._thread_locks

    def test_get_thread_lock_returns_existing(self, reset_app_state_globals):
        """Test getting thread lock returns existing lock."""
        thread_id = "test-thread-123"
        existing_lock = asyncio.Lock()
        app_state._thread_locks[thread_id] = existing_lock

        lock = app_state.get_thread_lock(thread_id)

        assert lock is existing_lock


class TestLastEmittedText:
    """Test last emitted text management."""

    def test_get_last_emitted_text_existing(self, reset_app_state_globals):
        """Test getting existing last emitted text."""
        thread_id = "test-thread-123"
        text = "Last message"
        app_state._last_emitted_text[thread_id] = text

        result = app_state.get_last_emitted_text(thread_id)

        assert result == text

    def test_get_last_emitted_text_nonexistent(self, reset_app_state_globals):
        """Test getting nonexistent last emitted text returns empty string."""
        result = app_state.get_last_emitted_text("nonexistent-thread")

        assert result == ""

    def test_set_last_emitted_text(self, reset_app_state_globals):
        """Test setting last emitted text."""
        thread_id = "test-thread-123"
        text = "New message"

        app_state.set_last_emitted_text(thread_id, text)

        assert app_state._last_emitted_text[thread_id] == text

    def test_set_last_emitted_text_none_converts_to_empty(self, reset_app_state_globals):
        """Test setting None as last emitted text converts to empty string."""
        thread_id = "test-thread-123"

        app_state.set_last_emitted_text(thread_id, None)

        assert app_state._last_emitted_text[thread_id] == ""


class TestFinanceSamplesCache:
    """Test finance samples caching functionality."""

    def test_set_finance_samples(self, reset_app_state_globals):
        """Test setting finance samples in cache."""
        user_id = uuid4()
        tx_samples = '["tx1", "tx2"]'
        asset_samples = '["asset1"]'
        liability_samples = '["liability1"]'
        account_samples = '["account1"]'

        app_state.set_finance_samples(user_id, tx_samples, asset_samples, liability_samples, account_samples)

        assert str(user_id) in app_state._finance_samples_cache
        cache_entry = app_state._finance_samples_cache[str(user_id)]
        assert cache_entry["tx_samples"] == tx_samples
        assert cache_entry["asset_samples"] == asset_samples
        assert cache_entry["liability_samples"] == liability_samples
        assert cache_entry["account_samples"] == account_samples
        assert "cached_at" in cache_entry

    def test_get_finance_samples_fresh(self, reset_app_state_globals):
        """Test getting fresh finance samples from cache."""
        user_id = uuid4()
        tx_samples = '["tx1"]'
        asset_samples = '["asset1"]'
        liability_samples = '["liability1"]'
        account_samples = '["account1"]'

        app_state.set_finance_samples(user_id, tx_samples, asset_samples, liability_samples, account_samples)

        result = app_state.get_finance_samples(user_id)

        assert result is not None
        assert result == (tx_samples, asset_samples, liability_samples, account_samples)

    def test_get_finance_samples_expired(self, reset_app_state_globals):
        """Test getting expired finance samples returns None."""
        user_id = uuid4()
        app_state._finance_samples_cache[str(user_id)] = {
            "tx_samples": '["tx1"]',
            "asset_samples": '["asset1"]',
            "liability_samples": '["liability1"]',
            "account_samples": '["account1"]',
            "cached_at": time.time() - (app_state.FINANCE_SAMPLES_CACHE_TTL_SECONDS + 100)
        }

        result = app_state.get_finance_samples(user_id)

        assert result is None

    def test_get_finance_samples_nonexistent(self, reset_app_state_globals):
        """Test getting nonexistent finance samples returns None."""
        user_id = uuid4()

        result = app_state.get_finance_samples(user_id)

        assert result is None

    def test_invalidate_finance_samples(self, reset_app_state_globals):
        """Test invalidating finance samples."""
        user_id = uuid4()
        app_state._finance_samples_cache[str(user_id)] = {
            "tx_samples": '["tx1"]',
            "cached_at": time.time()
        }

        app_state.invalidate_finance_samples(user_id)

        assert str(user_id) not in app_state._finance_samples_cache


class TestFinanceAgentCache:
    """Test finance agent caching functionality."""

    def test_set_cached_finance_agent(self, reset_app_state_globals):
        """Test setting cached finance agent."""
        user_id = uuid4()
        mock_agent = Mock()

        app_state.set_cached_finance_agent(user_id, mock_agent)

        assert str(user_id) in app_state._finance_agent_cache
        cache_entry = app_state._finance_agent_cache[str(user_id)]
        assert cache_entry["agent"] == mock_agent
        assert "cached_at" in cache_entry

    def test_get_cached_finance_agent_fresh(self, reset_app_state_globals):
        """Test getting fresh cached finance agent."""
        user_id = uuid4()
        mock_agent = Mock()
        app_state.set_cached_finance_agent(user_id, mock_agent)

        result = app_state.get_cached_finance_agent(user_id)

        assert result == mock_agent

    def test_get_cached_finance_agent_expired(self, reset_app_state_globals):
        """Test getting expired cached finance agent returns None."""
        user_id = uuid4()
        app_state._finance_agent_cache[str(user_id)] = {
            "agent": Mock(),
            "cached_at": time.time() - (app_state.FINANCE_AGENT_CACHE_TTL_SECONDS + 100)
        }

        result = app_state.get_cached_finance_agent(user_id)

        assert result is None
        assert str(user_id) not in app_state._finance_agent_cache

    def test_get_cached_finance_agent_nonexistent(self, reset_app_state_globals):
        """Test getting nonexistent cached finance agent returns None."""
        user_id = uuid4()

        result = app_state.get_cached_finance_agent(user_id)

        assert result is None

    def test_cleanup_expired_finance_agents(self, reset_app_state_globals):
        """Test cleanup of expired finance agents."""
        user_id1 = uuid4()
        user_id2 = uuid4()
        user_id3 = uuid4()

        app_state._finance_agent_cache[str(user_id1)] = {
            "agent": Mock(),
            "cached_at": time.time()
        }

        app_state._finance_agent_cache[str(user_id2)] = {
            "agent": Mock(),
            "cached_at": time.time() - (app_state.FINANCE_AGENT_CACHE_TTL_SECONDS + 100)
        }
        app_state._finance_agent_cache[str(user_id3)] = {
            "agent": Mock(),
            "cached_at": time.time() - (app_state.FINANCE_AGENT_CACHE_TTL_SECONDS + 200)
        }

        removed_count = app_state.cleanup_expired_finance_agents()

        assert removed_count == 2
        assert str(user_id1) in app_state._finance_agent_cache
        assert str(user_id2) not in app_state._finance_agent_cache
        assert str(user_id3) not in app_state._finance_agent_cache

    def test_cleanup_expired_finance_agents_handles_invalid_timestamp(self, reset_app_state_globals):
        """Test cleanup handles invalid cached_at values gracefully."""
        user_id = uuid4()
        app_state._finance_agent_cache[str(user_id)] = {
            "agent": Mock(),
            "cached_at": "invalid"
        }

        removed_count = app_state.cleanup_expired_finance_agents()

        assert removed_count >= 0

    def test_invalidate_finance_agent(self, reset_app_state_globals):
        """Test invalidating finance agent."""
        user_id = uuid4()
        app_state._finance_agent_cache[str(user_id)] = {
            "agent": Mock(),
            "cached_at": time.time()
        }

        app_state.invalidate_finance_agent(user_id)

        assert str(user_id) not in app_state._finance_agent_cache


class TestWealthAgentCache:
    """Test wealth agent caching functionality."""

    def test_set_cached_wealth_agent(self, reset_app_state_globals):
        """Test setting cached wealth agent."""
        user_id = uuid4()
        mock_agent = Mock()

        app_state.set_cached_wealth_agent(user_id, mock_agent)

        assert str(user_id) in app_state._wealth_agent_cache
        cache_entry = app_state._wealth_agent_cache[str(user_id)]
        assert cache_entry["agent"] == mock_agent
        assert "cached_at" in cache_entry

    def test_get_cached_wealth_agent_fresh(self, reset_app_state_globals):
        """Test getting fresh cached wealth agent."""
        user_id = uuid4()
        mock_agent = Mock()
        app_state.set_cached_wealth_agent(user_id, mock_agent)

        result = app_state.get_cached_wealth_agent(user_id)

        assert result == mock_agent

    def test_get_cached_wealth_agent_expired(self, reset_app_state_globals):
        """Test getting expired cached wealth agent returns None."""
        user_id = uuid4()
        app_state._wealth_agent_cache[str(user_id)] = {
            "agent": Mock(),
            "cached_at": time.time() - (app_state.WEALTH_AGENT_CACHE_TTL_SECONDS + 100)
        }

        result = app_state.get_cached_wealth_agent(user_id)

        assert result is None
        assert str(user_id) not in app_state._wealth_agent_cache

    def test_cleanup_expired_wealth_agents(self, reset_app_state_globals):
        """Test cleanup of expired wealth agents."""
        user_id1 = uuid4()
        user_id2 = uuid4()

        app_state._wealth_agent_cache[str(user_id1)] = {
            "agent": Mock(),
            "cached_at": time.time()
        }
        app_state._wealth_agent_cache[str(user_id2)] = {
            "agent": Mock(),
            "cached_at": time.time() - (app_state.WEALTH_AGENT_CACHE_TTL_SECONDS + 100)
        }

        removed_count = app_state.cleanup_expired_wealth_agents()

        assert removed_count == 1
        assert str(user_id1) in app_state._wealth_agent_cache
        assert str(user_id2) not in app_state._wealth_agent_cache


class TestUserThreadFunctions:
    """Test user thread related functions."""

    def test_find_user_threads(self, reset_app_state_globals):
        """Test finding threads for a user."""
        user_id = uuid4()
        other_user_id = uuid4()

        mock_state1 = Mock()
        mock_state1.user_id = user_id
        mock_state2 = Mock()
        mock_state2.user_id = user_id
        mock_state3 = Mock()
        mock_state3.user_id = other_user_id

        app_state._onboarding_threads["thread1"] = mock_state1
        app_state._onboarding_threads["thread2"] = mock_state2
        app_state._onboarding_threads["thread3"] = mock_state3

        result = app_state.find_user_threads(user_id)

        assert len(result) == 2
        thread_ids = [tid for tid, _ in result]
        assert "thread1" in thread_ids
        assert "thread2" in thread_ids
        assert "thread3" not in thread_ids

    def test_get_onboarding_status_for_user_no_threads(self, reset_app_state_globals):
        """Test getting onboarding status for user with no threads."""
        user_id = uuid4()

        result = app_state.get_onboarding_status_for_user(user_id)

        assert result["active"] is False
        assert result["onboarding_done"] is False
        assert result["thread_id"] is None
        assert result["current_flow_step"] is None

    def test_get_onboarding_status_for_user_active(self, reset_app_state_globals):
        """Test getting onboarding status for user with active onboarding."""
        user_id = uuid4()
        mock_state = Mock()
        mock_state.user_id = user_id
        mock_state.turn_number = 5
        mock_user_context = Mock()
        mock_user_context.ready_for_orchestrator = False
        mock_state.user_context = mock_user_context
        mock_flow_step = Mock()
        mock_flow_step.value = "collecting_profile"
        mock_state.current_flow_step = mock_flow_step

        app_state._onboarding_threads["thread1"] = mock_state

        result = app_state.get_onboarding_status_for_user(user_id)

        assert result["active"] is True
        assert result["onboarding_done"] is False
        assert result["thread_id"] == "thread1"
        assert result["current_flow_step"] == "collecting_profile"

    def test_get_onboarding_status_for_user_done(self, reset_app_state_globals):
        """Test getting onboarding status for user with completed onboarding."""
        user_id = uuid4()
        mock_state = Mock()
        mock_state.user_id = user_id
        mock_state.turn_number = 10
        mock_user_context = Mock()
        mock_user_context.ready_for_orchestrator = True
        mock_state.user_context = mock_user_context

        app_state._onboarding_threads["thread1"] = mock_state

        result = app_state.get_onboarding_status_for_user(user_id)

        assert result["active"] is False
        assert result["onboarding_done"] is True
        assert result["thread_id"] is None
        assert result["current_flow_step"] is None


class TestAWSClients:
    """Test AWS client singleton functions."""

    def test_aws_client_getters_create_singletons(self, reset_app_state_globals, mock_env_vars):
        """Test that AWS client getters create singleton instances."""
        with patch('boto3.client') as mock_boto_client, \
             patch('app.services.nudges.fos_manager.FOSNudgeManager') as mock_fos_class:
            mock_client = Mock()
            mock_boto_client.return_value = mock_client
            mock_fos = Mock()
            mock_fos_class.return_value = mock_fos

            bedrock1 = app_state.get_bedrock_runtime_client()
            bedrock2 = app_state.get_bedrock_runtime_client()
            s3v1 = app_state.get_s3vectors_client()
            s3v2 = app_state.get_s3vectors_client()
            s3_1 = app_state.get_s3_client()
            s3_2 = app_state.get_s3_client()
            fos1 = app_state.get_fos_nudge_manager()
            fos2 = app_state.get_fos_nudge_manager()

            assert bedrock1 == mock_client and bedrock2 == mock_client
            assert s3v1 == mock_client and s3v2 == mock_client
            assert s3_1 == mock_client and s3_2 == mock_client
            assert fos1 == mock_fos and fos2 == mock_fos
            assert mock_boto_client.call_count == 3
            mock_fos_class.assert_called_once()


class TestAWSClientManagement:
    """Test AWS client management functions."""

    @pytest.mark.asyncio
    async def test_warmup_aws_clients_success(self, reset_app_state_globals, mock_env_vars):
        """Test successful warmup of AWS clients."""
        with patch('boto3.client') as mock_boto_client:
            mock_client = Mock()
            mock_boto_client.return_value = mock_client

            await app_state.warmup_aws_clients()

            assert app_state._bedrock_runtime_client is not None
            assert app_state._s3vectors_client is not None
            assert app_state._s3_client is not None

    @pytest.mark.asyncio
    async def test_warmup_aws_clients_handles_errors(self, reset_app_state_globals, mock_env_vars):
        """Test warmup handles errors gracefully."""
        with patch('boto3.client', side_effect=Exception("AWS error")):
            await app_state.warmup_aws_clients()

    def test_dispose_aws_clients(self, reset_app_state_globals, mock_env_vars):
        """Test disposing AWS clients."""
        with patch('boto3.client') as mock_boto_client:
            mock_client = Mock()
            mock_boto_client.return_value = mock_client

            app_state.get_bedrock_runtime_client()
            app_state.get_s3vectors_client()
            app_state.get_s3_client()

            app_state.dispose_aws_clients()

            assert app_state._bedrock_runtime_client is None
            assert app_state._s3vectors_client is None
            assert app_state._s3_client is None


class TestFinanceAgentCleanupTask:
    """Test finance agent cleanup task management."""

    @pytest.mark.asyncio
    async def test_start_finance_agent_cleanup_task(self, reset_app_state_globals):
        """Test starting finance agent cleanup task."""
        await app_state.start_finance_agent_cleanup_task()

        assert app_state._finance_agent_cleanup_task is not None
        assert isinstance(app_state._finance_agent_cleanup_task, asyncio.Task)

        app_state._finance_agent_cleanup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await app_state._finance_agent_cleanup_task

    def test_dispose_finance_agent_cleanup_task_active_task(self, reset_app_state_globals):
        """Test disposing active cleanup task."""
        mock_task = Mock()
        mock_task.done.return_value = False
        app_state._finance_agent_cleanup_task = mock_task

        app_state.dispose_finance_agent_cleanup_task()

        mock_task.cancel.assert_called_once()
        assert app_state._finance_agent_cleanup_task is None

    def test_dispose_finance_agent_cleanup_task_no_task(self, reset_app_state_globals):
        """Test disposing when no task exists."""
        app_state.dispose_finance_agent_cleanup_task()

    def test_dispose_finance_agent_cleanup_task_handles_errors(self, reset_app_state_globals):
        """Test dispose handles errors gracefully."""
        mock_task = Mock()
        mock_task.done.side_effect = Exception("Task error")
        app_state._finance_agent_cleanup_task = mock_task

        app_state.dispose_finance_agent_cleanup_task()
