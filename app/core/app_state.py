from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, Optional, Tuple
from uuid import UUID

from langgraph.graph.state import CompiledStateGraph

if TYPE_CHECKING:
    from app.agents.onboarding import OnboardingAgent, OnboardingState

_onboarding_agent: "OnboardingAgent | None" = None
_supervisor_graph = None
_user_sessions: "dict[UUID, OnboardingState]" = {}

_onboarding_threads: "dict[str, OnboardingState]" = {}
_sse_queues: dict[str, asyncio.Queue] = {}
_audio_queues: dict[str, asyncio.Queue] = {}
_thread_locks: dict[str, asyncio.Lock] = {}

_last_emitted_text: dict[str, str] = {}

# Finance samples cache (per-user) - stores compact JSON strings and timestamps
FINANCE_SAMPLES_CACHE_TTL_SECONDS: int = 600
_finance_samples_cache: dict[str, dict[str, Any]] = {}

# Finance agent cache (per-user) - stores LangGraph agents with TTL
FINANCE_AGENT_CACHE_TTL_SECONDS: int = 3600  # 1 hour
_finance_agent_cache: dict[str, dict[str, Any]] = {}

WEALTH_AGENT_CACHE_TTL_SECONDS: int = 3600  # 1 hour
_wealth_agent_cache: dict[str, dict[str, Any]] = {}

_finance_agent: "CompiledStateGraph | None" = None

_wealth_agent: "CompiledStateGraph | None" = None

_goal_agent: "CompiledStateGraph | None" = None

# AWS Clients - Singleton pattern
_bedrock_runtime_client: Any | None = None
_s3vectors_client: Any | None = None
_s3_client: Any | None = None

# FOS Nudge Manager - Singleton pattern
_fos_nudge_manager: Any | None = None

# Finance agent cleanup task
_finance_agent_cleanup_task: Optional[asyncio.Task] = None


def get_onboarding_agent() -> OnboardingAgent:
    from app.agents.onboarding import OnboardingAgent

    global _onboarding_agent
    if _onboarding_agent is None:
        _onboarding_agent = OnboardingAgent()
    return _onboarding_agent


def get_supervisor_graph() -> CompiledStateGraph:
    global _supervisor_graph
    if _supervisor_graph is None:
        from app.agents.supervisor import compile_supervisor_graph

        _supervisor_graph = compile_supervisor_graph()
    return _supervisor_graph


def get_finance_agent():
    """Get the global finance agent instance (singleton pattern)."""
    from app.agents.supervisor.finance_agent.agent import FinanceAgent

    global _finance_agent
    if _finance_agent is None:
        _finance_agent = FinanceAgent()
    return _finance_agent


def get_wealth_agent():
    """Get the global wealth agent instance (singleton pattern)."""
    from app.agents.supervisor.wealth_agent.agent import WealthAgent

    global _wealth_agent
    if _wealth_agent is None:
        _wealth_agent = WealthAgent()
    return _wealth_agent


def get_wealth_agent_graph():
    """Get the compiled wealth agent graph."""
    from app.agents.supervisor.wealth_agent.agent import compile_wealth_agent_graph

    return compile_wealth_agent_graph()


def get_goal_agent_graph() -> CompiledStateGraph:
    """Get the compiled goal agent graph."""
    from app.agents.supervisor.goal_agent.agent import compile_goal_agent_graph
    return compile_goal_agent_graph()


def get_goal_agent():
    """Get goal agent instance."""
    from app.agents.supervisor.goal_agent.agent import get_goal_agent

    return get_goal_agent()


def register_thread(thread_id: str, state: OnboardingState) -> None:
    _onboarding_threads[thread_id] = state


def get_thread_state(thread_id: str) -> OnboardingState | None:
    return _onboarding_threads.get(thread_id)


def set_thread_state(thread_id: str, state: OnboardingState) -> None:
    _onboarding_threads[thread_id] = state


def get_sse_queue(thread_id: str) -> asyncio.Queue[str]:
    if thread_id not in _sse_queues:
        _sse_queues[thread_id] = asyncio.Queue()
    return _sse_queues[thread_id]


def drop_sse_queue(thread_id: str) -> None:
    _sse_queues.pop(thread_id, None)


def get_thread_lock(thread_id: str) -> asyncio.Lock:
    lock = _thread_locks.get(thread_id)
    if lock is None:
        lock = asyncio.Lock()
        _thread_locks[thread_id] = lock
    return lock


def get_last_emitted_text(thread_id: str) -> str:
    return _last_emitted_text.get(thread_id, "")


def set_last_emitted_text(thread_id: str, text: str) -> None:
    if text is None:
        text = ""
    _last_emitted_text[thread_id] = text


def get_finance_samples(user_id: UUID) -> Optional[Tuple[str, str, str, str]]:
    """Return cached (tx_samples_json, asset_samples_json, liability_samples_json, account_samples_json) if fresh, else None."""
    try:
        entry = _finance_samples_cache.get(str(user_id))
        if not entry:
            return None
        cached_at = entry.get("cached_at", 0)
        if (time.time() - float(cached_at)) > FINANCE_SAMPLES_CACHE_TTL_SECONDS:
            return None
        tx_samples = entry.get("tx_samples") or "[]"
        asset_samples = entry.get("asset_samples") or "[]"
        liability_samples = entry.get("liability_samples") or "[]"
        account_samples = entry.get("account_samples") or "[]"
        if (
            isinstance(tx_samples, str)
            and isinstance(asset_samples, str)
            and isinstance(liability_samples, str)
            and isinstance(account_samples, str)
        ):
            return tx_samples, asset_samples, liability_samples, account_samples
        return None
    except Exception:
        return None


def set_finance_samples(user_id: UUID, tx_samples_json: str, asset_samples_json: str, liability_samples_json: str, account_samples_json: str) -> None:
    """Cache finance samples for a user (compact JSON strings)."""
    _finance_samples_cache[str(user_id)] = {
        "tx_samples": tx_samples_json or "[]",
        "asset_samples": asset_samples_json or "[]",
        "liability_samples": liability_samples_json or "[]",
        "account_samples": account_samples_json or "[]",
        "cached_at": time.time(),
    }


def invalidate_finance_samples(user_id: UUID) -> None:
    """Invalidate cached finance samples for a user."""
    _finance_samples_cache.pop(str(user_id), None)


def get_cached_finance_agent(user_id: UUID) -> "CompiledStateGraph | None":
    """Get cached finance agent for a user if it exists and hasn't expired."""
    cache_key = str(user_id)
    entry = _finance_agent_cache.get(cache_key)

    if not entry:
        return None

    # Check if cache entry has expired
    cached_at = entry.get("cached_at", 0)
    if (time.time() - cached_at) > FINANCE_AGENT_CACHE_TTL_SECONDS:
        # Remove expired entry
        _finance_agent_cache.pop(cache_key, None)
        return None

    return entry.get("agent")


def set_cached_finance_agent(user_id: UUID, agent: "CompiledStateGraph") -> None:
    """Cache a finance agent for a user with current timestamp."""
    _finance_agent_cache[str(user_id)] = {
        "agent": agent,
        "cached_at": time.time()
    }


def cleanup_expired_finance_agents() -> int:
    """Clean up expired finance agent cache entries. Returns number of entries removed."""
    current_time = time.time()
    expired_keys = []

    for user_id, entry in _finance_agent_cache.items():
        cached_at_raw = entry.get("cached_at")
        try:
            cached_at = float(cached_at_raw) if cached_at_raw is not None else 0.0
        except (TypeError, ValueError):
            cached_at = 0.0

        if (current_time - cached_at) > FINANCE_AGENT_CACHE_TTL_SECONDS:
            expired_keys.append(user_id)

    for key in expired_keys:
        _finance_agent_cache.pop(key, None)

    return len(expired_keys)


def get_cached_wealth_agent(user_id: UUID) -> "CompiledStateGraph | None":
    """Get cached wealth agent for a user if it exists and hasn't expired."""
    cache_key = str(user_id)
    entry = _wealth_agent_cache.get(cache_key)

    if not entry:
        return None

    cached_at = entry.get("cached_at", 0)
    if (time.time() - cached_at) > WEALTH_AGENT_CACHE_TTL_SECONDS:
        _wealth_agent_cache.pop(cache_key, None)
        return None

    return entry.get("agent")


def set_cached_wealth_agent(user_id: UUID, agent: "CompiledStateGraph") -> None:
    """Cache a wealth agent for a user with current timestamp."""
    _wealth_agent_cache[str(user_id)] = {
        "agent": agent,
        "cached_at": time.time()
    }


def cleanup_expired_wealth_agents() -> int:
    """Clean up expired wealth agent cache entries. Returns number of entries removed."""
    current_time = time.time()
    expired_keys = []

    for user_id, entry in _wealth_agent_cache.items():
        cached_at = entry.get("cached_at", 0)
        if (current_time - cached_at) > WEALTH_AGENT_CACHE_TTL_SECONDS:
            expired_keys.append(user_id)

    for key in expired_keys:
        _wealth_agent_cache.pop(key, None)

    return len(expired_keys)


def invalidate_finance_agent(user_id: UUID) -> None:
    """Invalidate cached finance agent for a user."""
    _finance_agent_cache.pop(str(user_id), None)


def find_user_threads(user_id: UUID) -> list[tuple[str, "OnboardingState"]]:
    return [(tid, st) for tid, st in _onboarding_threads.items() if getattr(st, "user_id", None) == user_id]


def get_onboarding_status_for_user(user_id: UUID) -> dict:
    threads = find_user_threads(user_id)
    if not threads:
        return {
            "active": False,
            "onboarding_done": False,
            "thread_id": None,
            "current_flow_step": None,
        }

    def _score(item: tuple[str, "OnboardingState"]) -> int:
        tid, st = item
        try:
            return int(getattr(st, "turn_number", 0))
        except Exception:
            return len(getattr(st, "conversation_history", []) or [])

    latest_tid, latest_st = max(threads, key=_score)

    done = bool(getattr(latest_st.user_context, "ready_for_orchestrator", False))

    return {
        "active": not done,
        "onboarding_done": done,
        "thread_id": latest_tid if not done else None,
        "current_flow_step": getattr(latest_st.current_flow_step, "value", None) if not done else None,
    }


def get_bedrock_runtime_client() -> Any:
    """Get AWS Bedrock Runtime client with connection pooling (singleton pattern)."""
    global _bedrock_runtime_client
    if _bedrock_runtime_client is None:
        import boto3
        from botocore.config import Config

        from app.core.config import config

        region = config.AWS_REGION
        client_config = Config(
            region_name=region,
            retries={'max_attempts': 3, 'mode': 'standard'},
            max_pool_connections=20,  # Connection pool size
            connect_timeout=10,
            read_timeout=60,
        )

        _bedrock_runtime_client = boto3.client(
            'bedrock-runtime',
            config=client_config
        )

    return _bedrock_runtime_client


def get_s3vectors_client() -> Any:
    """Get AWS S3Vectors client with connection pooling (singleton pattern)."""
    global _s3vectors_client
    if _s3vectors_client is None:
        import boto3
        from botocore.config import Config

        from app.core.config import config

        region = config.AWS_REGION
        client_config = Config(
            region_name=region,
            retries={'max_attempts': 3, 'mode': 'standard'},
            max_pool_connections=20,  # Connection pool size
            connect_timeout=10,
            read_timeout=60,
        )

        _s3vectors_client = boto3.client(
            's3vectors',
            config=client_config
        )

    return _s3vectors_client


def get_s3_client() -> Any:
    """Get AWS S3 client with connection pooling (singleton pattern)."""
    global _s3_client
    if _s3_client is None:
        import boto3
        from botocore.config import Config

        from app.core.config import config

        region = config.AWS_REGION
        client_config = Config(
            region_name=region,
            retries={'max_attempts': 3, 'mode': 'standard'},
            max_pool_connections=20,  # Connection pool size
            connect_timeout=10,
            read_timeout=60,
        )

        _s3_client = boto3.client(
            's3',
            config=client_config
        )

    return _s3_client


def get_fos_nudge_manager():
    """Get FOS nudge manager instance (singleton pattern)."""
    global _fos_nudge_manager
    if _fos_nudge_manager is None:
        from app.services.nudges.fos_manager import FOSNudgeManager
        _fos_nudge_manager = FOSNudgeManager()
    return _fos_nudge_manager


async def warmup_aws_clients() -> None:
    """Warm up AWS clients during app startup to avoid first-request latency."""
    try:
        # Initialize clients in parallel
        import asyncio
        await asyncio.gather(
            asyncio.get_event_loop().run_in_executor(None, get_bedrock_runtime_client),
            asyncio.get_event_loop().run_in_executor(None, get_s3vectors_client),
            asyncio.get_event_loop().run_in_executor(None, get_s3_client)
        )
    except Exception as e:
        # Don't fail app startup if warmup fails
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"AWS client warmup failed: {e}")


async def start_finance_agent_cleanup_task() -> None:
    """Start periodic cleanup of expired finance agents."""
    import asyncio

    async def cleanup_task():
        while True:
            try:
                await asyncio.sleep(1800)  # Clean up every 30 minutes
                removed_count = cleanup_expired_finance_agents()
                if removed_count > 0:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f"Cleaned up {removed_count} expired finance agents")
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Finance agent cleanup error: {e}")

    # Start the cleanup task
    cleanup_task_instance = asyncio.create_task(cleanup_task())

    # Store reference to prevent garbage collection
    global _finance_agent_cleanup_task
    _finance_agent_cleanup_task = cleanup_task_instance


def dispose_aws_clients() -> None:
    """Dispose of AWS clients for cleanup (call during app shutdown)."""
    global _bedrock_runtime_client, _s3vectors_client, _s3_client

    try:
        if _bedrock_runtime_client:
            # boto3 clients don't have explicit dispose, but we can clear reference
            _bedrock_runtime_client = None
    except Exception:
        pass

    try:
        if _s3vectors_client:
            _s3vectors_client = None
    except Exception:
        pass

    try:
        if _s3_client:
            _s3_client = None
    except Exception:
        pass


def dispose_finance_agent_cleanup_task() -> None:
    """Dispose of finance agent cleanup task (call during app shutdown)."""
    global _finance_agent_cleanup_task

    try:
        if _finance_agent_cleanup_task and not _finance_agent_cleanup_task.done():
            _finance_agent_cleanup_task.cancel()
            import logging
            logger = logging.getLogger(__name__)
            logger.info("Finance agent cleanup task cancelled")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error cancelling finance agent cleanup task: {e}")
    finally:
        _finance_agent_cleanup_task = None


def reset_agents() -> dict[str, int]:
    """Reset all agent instances and caches.

    This function clears:
    - Global agent singletons (_onboarding_agent, _supervisor_graph, _finance_agent, _wealth_agent, _goal_agent)
    - Per-user agent caches (_finance_agent_cache, _wealth_agent_cache)
    - User sessions and threads (_user_sessions, _onboarding_threads, _sse_queues, _thread_locks, _last_emitted_text)
    - Finance samples cache (_finance_samples_cache)

    Returns:
        dict: Summary of what was cleared with counts

    Note: This does not clear AWS clients or FOS nudge manager as they are expensive to recreate.

    """
    import logging
    logger = logging.getLogger(__name__)

    # Track what we're clearing
    cleared_counts = {}

    # Clear global agent singletons
    global _onboarding_agent, _supervisor_graph, _finance_agent, _wealth_agent, _goal_agent

    agent_globals = [
        ("onboarding_agent", "_onboarding_agent"),
        ("supervisor_graph", "_supervisor_graph"),
        ("finance_agent", "_finance_agent"),
        ("wealth_agent", "_wealth_agent"),
        ("goal_agent", "_goal_agent"),
    ]
    for key, var_name in agent_globals:
        if globals()[var_name] is not None:
            globals()[var_name] = None
            cleared_counts[key] = 1
        else:
            cleared_counts[key] = 0
    # Clear per-user agent caches
    finance_agents_cleared = len(_finance_agent_cache)
    _finance_agent_cache.clear()
    cleared_counts["finance_agent_cache"] = finance_agents_cleared

    wealth_agents_cleared = len(_wealth_agent_cache)
    _wealth_agent_cache.clear()
    cleared_counts["wealth_agent_cache"] = wealth_agents_cleared

    # Clear finance samples cache
    finance_samples_cleared = len(_finance_samples_cache)
    _finance_samples_cache.clear()
    cleared_counts["finance_samples_cache"] = finance_samples_cleared

    # Clear user sessions and threads
    user_sessions_cleared = len(_user_sessions)
    _user_sessions.clear()
    cleared_counts["user_sessions"] = user_sessions_cleared

    onboarding_threads_cleared = len(_onboarding_threads)
    _onboarding_threads.clear()
    cleared_counts["onboarding_threads"] = onboarding_threads_cleared

    sse_queues_cleared = len(_sse_queues)
    _sse_queues.clear()
    cleared_counts["sse_queues"] = sse_queues_cleared

    thread_locks_cleared = len(_thread_locks)
    _thread_locks.clear()
    cleared_counts["thread_locks"] = thread_locks_cleared

    last_emitted_text_cleared = len(_last_emitted_text)
    _last_emitted_text.clear()
    cleared_counts["last_emitted_text"] = last_emitted_text_cleared

    # Clear guest agent LRU cache if available
    try:
        from app.agents.guest.agent import get_guest_graph
        get_guest_graph.cache_clear()
        cleared_counts["guest_graph_cache"] = 1
    except Exception as e:
        logger.warning(f"Could not clear guest graph cache: {e}")
        cleared_counts["guest_graph_cache"] = 0

    total_cleared = sum(cleared_counts.values())
    logger.info(f"Agent reset completed. Cleared {total_cleared} items: {cleared_counts}")

    return cleared_counts


# Audio queue management functions
def get_audio_queue(thread_id: str) -> asyncio.Queue:
    """Get or create audio queue for a thread.

    Args:
        thread_id: Unique thread identifier

    Returns:
        asyncio.Queue: Audio queue for the thread

    """
    if thread_id not in _audio_queues:
        _audio_queues[thread_id] = asyncio.Queue()
    return _audio_queues[thread_id]


def drop_audio_queue(thread_id: str) -> None:
    """Drop audio queue for a thread.

    Args:
        thread_id: Unique thread identifier

    """
    if thread_id in _audio_queues:
        del _audio_queues[thread_id]
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[AUDIO QUEUE] Dropped audio queue for thread_id: {thread_id}")


def get_audio_queue_count() -> int:
    """Get the number of active audio queues.

    Returns:
        int: Number of active audio queues

    """
    return len(_audio_queues)


def cleanup_audio_queues() -> int:
    """Clean up empty audio queues.

    Returns:
        int: Number of queues cleaned up

    """
    empty_queues = []
    for thread_id, queue in _audio_queues.items():
        if queue.empty():
            empty_queues.append(thread_id)

    for thread_id in empty_queues:
        del _audio_queues[thread_id]

    if empty_queues:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[AUDIO QUEUE] Cleaned up {len(empty_queues)} empty audio queues")

    return len(empty_queues)
