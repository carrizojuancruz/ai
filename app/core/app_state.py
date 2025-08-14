from __future__ import annotations

from typing import Dict, Optional
from uuid import UUID
import asyncio

from app.agents.onboarding import OnboardingAgent, OnboardingState


_onboarding_agent: OnboardingAgent | None = None
_user_sessions: Dict[UUID, OnboardingState] = {}

_onboarding_threads: Dict[str, OnboardingState] = {}
_sse_queues: Dict[str, asyncio.Queue] = {}


def get_onboarding_agent() -> OnboardingAgent:
    global _onboarding_agent
    if _onboarding_agent is None:
        _onboarding_agent = OnboardingAgent()
    return _onboarding_agent


def get_user_sessions() -> Dict[UUID, OnboardingState]:
    return _user_sessions


def register_thread(thread_id: str, state: OnboardingState) -> None:
    _onboarding_threads[thread_id] = state


def get_thread_state(thread_id: str) -> Optional[OnboardingState]:
    return _onboarding_threads.get(thread_id)


def set_thread_state(thread_id: str, state: OnboardingState) -> None:
    _onboarding_threads[thread_id] = state


def get_sse_queue(thread_id: str) -> asyncio.Queue[str]:
    if thread_id not in _sse_queues:
        _sse_queues[thread_id] = asyncio.Queue()
    return _sse_queues[thread_id]


def drop_sse_queue(thread_id: str) -> None:
    _sse_queues.pop(thread_id, None)
