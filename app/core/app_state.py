from __future__ import annotations

from typing import Dict
from uuid import UUID

from app.agents.onboarding import OnboardingAgent, OnboardingState


_onboarding_agent: OnboardingAgent | None = None
_user_sessions: Dict[UUID, OnboardingState] = {}


def get_onboarding_agent() -> OnboardingAgent:
    global _onboarding_agent
    if _onboarding_agent is None:
        _onboarding_agent = OnboardingAgent()
    return _onboarding_agent


def get_user_sessions() -> Dict[UUID, OnboardingState]:
    return _user_sessions
