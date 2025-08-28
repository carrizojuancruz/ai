from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

from langgraph.graph.state import CompiledStateGraph

if TYPE_CHECKING:
    from app.agents.onboarding import OnboardingAgent, OnboardingState

_onboarding_agent: "OnboardingAgent | None" = None
_supervisor_graph = None
_user_sessions: "dict[UUID, OnboardingState]" = {}

_onboarding_threads: "dict[str, OnboardingState]" = {}
_sse_queues: dict[str, asyncio.Queue] = {}

_last_emitted_text: dict[str, str] = {}


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
