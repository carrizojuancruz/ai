"""Conftest for onboarding agent tests."""

import uuid
from unittest.mock import Mock

import pytest

from app.agents.onboarding.agent import OnboardingAgent
from app.agents.onboarding.state import OnboardingState
from app.agents.onboarding.types import FlowStep, InteractionType
from app.models import UserContext


@pytest.fixture
def sample_user_id():
    """Sample user ID for testing."""
    return uuid.uuid4()


@pytest.fixture
def sample_conversation_id():
    """Sample conversation ID for testing."""
    return uuid.uuid4()


@pytest.fixture
def basic_user_context():
    """Basic user context for testing."""
    return UserContext()


@pytest.fixture
def onboarding_state(sample_user_id, sample_conversation_id, basic_user_context):
    """Basic onboarding state for testing."""
    return OnboardingState(
        conversation_id=sample_conversation_id,
        user_id=sample_user_id,
        user_context=basic_user_context,
        current_flow_step=FlowStep.PRESENTATION,
        turn_number=0,
    )


@pytest.fixture
def onboarding_agent():
    """Onboarding agent instance for testing."""
    return OnboardingAgent()


@pytest.fixture
def mock_step_definition():
    """Mock step definition for testing."""
    mock_step = Mock()
    mock_step.id = FlowStep.PRESENTATION
    mock_step.message = "Welcome to onboarding!"
    mock_step.interaction_type = InteractionType.FREE_TEXT
    mock_step.choices = []
    mock_step.expected_field = None
    mock_step.validation = None
    mock_step.next_step = None
    return mock_step


@pytest.fixture
def presentation_state(onboarding_state):
    """Onboarding state at presentation step."""
    state = onboarding_state.model_copy()
    state.current_flow_step = FlowStep.PRESENTATION
    state.conversation_history = []
    return state


@pytest.fixture
def completed_onboarding_state(onboarding_state):
    """Onboarding state with completed onboarding."""
    state = onboarding_state.model_copy()
    state.current_flow_step = FlowStep.COMPLETE
    state.ready_for_completion = True
    state.user_context.preferred_name = "Test User"
    state.user_context.ready_for_orchestrator = True
    return state
