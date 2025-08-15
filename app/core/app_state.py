from __future__ import annotations

import asyncio
from uuid import UUID

from app.agents.onboarding import OnboardingAgent, OnboardingState
from app.agents.supervisor import compile_supervisor_graph

_onboarding_agent: OnboardingAgent | None = None
_supervisor_graph = None
_user_sessions: dict[UUID, OnboardingState] = {}

_onboarding_threads: dict[str, OnboardingState] = {}
_sse_queues: dict[str, asyncio.Queue] = {}

_last_emitted_text: dict[str, str] = {}


def get_onboarding_agent() -> OnboardingAgent:
    global _onboarding_agent
    if _onboarding_agent is None:
        _onboarding_agent = OnboardingAgent()
    return _onboarding_agent


def get_supervisor_graph():
    global _supervisor_graph
    if _supervisor_graph is None:
        _supervisor_graph = compile_supervisor_graph()
    return _supervisor_graph


def get_user_sessions() -> dict[UUID, OnboardingState]:
    return _user_sessions


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


def get_last_emitted_text(thread_id: str) -> str:
    return _last_emitted_text.get(thread_id, "")


def set_last_emitted_text(thread_id: str, text: str) -> None:
    if text is None:
        text = ""
    _last_emitted_text[thread_id] = text
