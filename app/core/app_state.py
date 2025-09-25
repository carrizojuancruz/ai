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
_thread_locks: dict[str, asyncio.Lock] = {}

_last_emitted_text: dict[str, str] = {}

# Finance samples cache (per-user) - stores compact JSON strings and timestamps
FINANCE_SAMPLES_CACHE_TTL_SECONDS: int = 600
_finance_samples_cache: dict[str, dict[str, Any]] = {}

# Finance agent cache (per-user) - stores LangGraph agents with TTL
FINANCE_AGENT_CACHE_TTL_SECONDS: int = 3600  # 1 hour
_finance_agent_cache: dict[str, dict[str, Any]] = {}

_finance_agent: "CompiledStateGraph | None" = None
_wealth_agent: "CompiledStateGraph | None" = None

# AWS Clients - Singleton pattern
_bedrock_runtime_client: Any | None = None
_s3vectors_client: Any | None = None
_s3_client: Any | None = None

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
    from app.agents.supervisor.wealth_agent.agent import compile_wealth_agent_graph

    global _wealth_agent
    if _wealth_agent is None:
        _wealth_agent = compile_wealth_agent_graph()
    return _wealth_agent


def get_goal_agent_graph() -> CompiledStateGraph:
    """Get the goal agent graph using singleton pattern for performance."""
    from app.agents.supervisor.goal_agent.agent import goal_agent_singleton

    return goal_agent_singleton.get_compiled_graph()


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


def get_finance_samples(user_id: UUID) -> Optional[Tuple[str, str]]:
    """Return cached (tx_samples_json, acct_samples_json) if fresh, else None."""
    try:
        entry = _finance_samples_cache.get(str(user_id))
        if not entry:
            return None
        cached_at = entry.get("cached_at", 0)
        if (time.time() - float(cached_at)) > FINANCE_SAMPLES_CACHE_TTL_SECONDS:
            return None
        tx_samples = entry.get("tx_samples") or "[]"
        acct_samples = entry.get("acct_samples") or "[]"
        if isinstance(tx_samples, str) and isinstance(acct_samples, str):
            return tx_samples, acct_samples
        return None
    except Exception:
        return None


def set_finance_samples(user_id: UUID, tx_samples_json: str, acct_samples_json: str) -> None:
    """Cache finance samples for a user (compact JSON strings)."""
    _finance_samples_cache[str(user_id)] = {
        "tx_samples": tx_samples_json or "[]",
        "acct_samples": acct_samples_json or "[]",
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
        cached_at = entry.get("cached_at", 0)
        if (current_time - cached_at) > FINANCE_AGENT_CACHE_TTL_SECONDS:
            expired_keys.append(user_id)

    for key in expired_keys:
        _finance_agent_cache.pop(key, None)

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
