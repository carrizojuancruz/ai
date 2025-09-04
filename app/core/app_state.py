from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
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

# AWS Clients - Singleton pattern
_bedrock_runtime_client: Any | None = None
_s3vectors_client: Any | None = None
_s3_client: Any | None = None


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


def find_user_threads(user_id: UUID) -> list[tuple[str, "OnboardingState"]]:
    return [(tid, st) for tid, st in _onboarding_threads.items() if getattr(st, "user_id", None) == user_id]


def get_onboarding_status_for_user(user_id: UUID) -> dict:
    threads = find_user_threads(user_id)
    if not threads:
        return {
            "active": False,
            "onboarding_done": False,
            "thread_id": None,
            "current_step": None,
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
        "current_step": getattr(latest_st.current_step, "value", None) if not done else None,
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
