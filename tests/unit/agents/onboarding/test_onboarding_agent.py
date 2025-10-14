"""Unit tests for onboarding agent."""

import uuid
from unittest.mock import patch

import pytest

from app.agents.onboarding.agent import OnboardingAgent, _generate_text_chunks
from app.agents.onboarding.state import OnboardingState
from app.agents.onboarding.types import FlowStep, InteractionType
from app.models import UserContext


class TestGenerateTextChunks:
    """Tests for _generate_text_chunks utility function."""

    def test_generate_text_chunks_empty_text(self):
        """Test generating chunks for empty text."""
        result = _generate_text_chunks("")
        assert result == []

    def test_generate_text_chunks_single_sentence(self):
        """Test generating chunks for a single sentence."""
        text = "This is a simple sentence."
        result = _generate_text_chunks(text)
        assert len(result) == 1
        assert result[0] == "This is a simple sentence."

    def test_generate_text_chunks_multiple_sentences(self):
        """Test generating chunks for multiple sentences."""
        text = "First sentence. Second sentence! Third sentence?"
        result = _generate_text_chunks(text)
        assert len(result) >= 1
        # Should preserve sentence endings
        assert any("." in chunk or "!" in chunk or "?" in chunk for chunk in result)

    def test_generate_text_chunks_long_sentence(self):
        """Test generating chunks for a long sentence."""
        # Create a long sentence with many words
        words = [f"word{i}" for i in range(50)]
        text = " ".join(words) + "."
        result = _generate_text_chunks(text, min_chunk=5, max_chunk=10)
        assert len(result) > 1
        # All chunks should be non-empty
        assert all(len(chunk.strip()) > 0 for chunk in result)

    def test_generate_text_chunks_custom_chunk_sizes(self):
        """Test generating chunks with custom min/max chunk sizes."""
        text = "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10."
        result = _generate_text_chunks(text, min_chunk=2, max_chunk=3)
        # Should create multiple chunks
        assert len(result) > 1

    def test_generate_text_chunks_chunk_joining_logic(self):
        """Test the chunk joining logic that handles punctuation and capitalization."""
        # Create text that will be split into chunks where:
        # - Some chunks end with punctuation (should trigger else branch)
        # - Some next chunks start with capital letters (should trigger if branch)
        # This should exercise both branches in the joining logic
        text = "Hello. This is a test! What follows is another sentence. and this continues normally without punctuation"
        result = _generate_text_chunks(text, min_chunk=3, max_chunk=8)

        # Should create multiple chunks
        assert len(result) > 1

        # Debug: print chunks to understand the joining logic
        print(f"Generated {len(result)} chunks:")
        for i, chunk in enumerate(result):
            print(f"  Chunk {i}: '{chunk}' (ends with: '{chunk[-1] if chunk else 'empty'}')")
            if i < len(result) - 1:
                next_chunk = result[i + 1]
                starts_upper = next_chunk[0].isupper() if next_chunk else False
                ends_punct = chunk[-1] in ".!?" if chunk else False
                condition = chunk and not ends_punct and next_chunk and starts_upper
                print(f"    Next: '{next_chunk[:20]}...' (starts upper: {starts_upper})")
                print(f"    Condition (ends punct: {ends_punct}): {condition}")

        # Verify that chunks are properly joined
        reconstructed = "".join(result).rstrip()
        assert reconstructed == text

    def test_generate_text_chunks_no_punctuation(self):
        """Test generating chunks when text has no sentence-ending punctuation."""
        # Text without . ! ? followed by spaces should use the word-based chunking (else branch)
        text = "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10"
        result = _generate_text_chunks(text, min_chunk=2, max_chunk=4)
        # Should create multiple chunks using word-based splitting
        assert len(result) > 1
        # All chunks should be joined properly
        reconstructed = "".join(result).rstrip()
        assert reconstructed == text


class TestOnboardingState:
    """Tests for OnboardingState class."""

    def test_onboarding_state_initialization(self, sample_user_id):
        """Test OnboardingState initialization with default values."""
        state = OnboardingState(user_id=sample_user_id)

        assert state.user_id == sample_user_id
        assert isinstance(state.conversation_id, uuid.UUID)
        assert state.current_flow_step == FlowStep.PRESENTATION
        assert state.turn_number == 0
        assert isinstance(state.user_context, UserContext)
        assert state.conversation_history == []
        assert state.last_user_message is None
        assert state.last_agent_response is None
        assert state.ready_for_completion is False
        assert state.current_interaction_type == InteractionType.FREE_TEXT
        assert state.current_choices == []

    def test_onboarding_state_custom_initialization(self, sample_user_id, sample_conversation_id):
        """Test OnboardingState initialization with custom values."""
        user_context = UserContext(preferred_name="Test User")
        state = OnboardingState(
            conversation_id=sample_conversation_id,
            user_id=sample_user_id,
            current_flow_step=FlowStep.STEP_1_CHOICE,
            turn_number=5,
            user_context=user_context,
        )

        assert state.conversation_id == sample_conversation_id
        assert state.user_id == sample_user_id
        assert state.current_flow_step == FlowStep.STEP_1_CHOICE
        assert state.turn_number == 5
        assert state.user_context.preferred_name == "Test User"

    def test_add_conversation_turn(self, onboarding_state):
        """Test adding a conversation turn to the history."""
        user_message = "Hello"
        agent_response = "Hi there!"

        onboarding_state.add_conversation_turn(user_message, agent_response)

        assert len(onboarding_state.conversation_history) == 1
        turn = onboarding_state.conversation_history[0]
        assert turn["turn_number"] == 0
        assert turn["user_message"] == user_message
        assert turn["agent_response"] == agent_response
        assert "timestamp" in turn
        assert onboarding_state.last_user_message == user_message
        assert onboarding_state.last_agent_response == agent_response
        assert onboarding_state.turn_number == 1

    def test_add_multiple_conversation_turns(self, onboarding_state):
        """Test adding multiple conversation turns."""
        # Add first turn
        onboarding_state.add_conversation_turn("Hello", "Hi!")
        assert onboarding_state.turn_number == 1
        assert len(onboarding_state.conversation_history) == 1

        # Add second turn
        onboarding_state.add_conversation_turn("How are you?", "I'm fine, thanks!")
        assert onboarding_state.turn_number == 2
        assert len(onboarding_state.conversation_history) == 2

        # Verify turn numbers are sequential
        assert onboarding_state.conversation_history[0]["turn_number"] == 0
        assert onboarding_state.conversation_history[1]["turn_number"] == 1

    def test_conversation_history_limit(self, onboarding_state):
        """Test that conversation history is limited to 50 turns."""
        # Add 55 turns
        for i in range(55):
            onboarding_state.add_conversation_turn(f"User {i}", f"Agent {i}")

        # Should only keep the last 50 turns
        assert len(onboarding_state.conversation_history) == 50
        assert onboarding_state.turn_number == 55

        # First kept turn should be turn 5 (55 - 50 = 5)
        assert onboarding_state.conversation_history[0]["turn_number"] == 5
        # Last turn should be turn 54
        assert onboarding_state.conversation_history[-1]["turn_number"] == 54

    def test_can_complete(self, onboarding_state):
        """Test can_complete with various conditions."""
        # Test without name - should return False
        onboarding_state.ready_for_completion = True
        assert onboarding_state.can_complete() is False

        # Test without ready flag - should return False
        onboarding_state.user_context.preferred_name = "Test User"
        onboarding_state.ready_for_completion = False
        assert onboarding_state.can_complete() is False

        # Test success case - both conditions met, should return True
        onboarding_state.user_context.preferred_name = "Test User"
        onboarding_state.ready_for_completion = True
        assert onboarding_state.can_complete() is True

    def test_ensure_completion_consistency(self, onboarding_state):
        """Test ensure_completion_consistency with various scenarios."""
        # Test 1: Sets ready_for_completion when user_context is ready
        onboarding_state.user_context.ready_for_orchestrator = True
        onboarding_state.ready_for_completion = False

        onboarding_state.ensure_completion_consistency()

        assert onboarding_state.ready_for_completion is True

        # Test 2: Preserves existing ready_for_completion when already true
        onboarding_state.user_context.ready_for_orchestrator = True
        onboarding_state.ready_for_completion = True

        onboarding_state.ensure_completion_consistency()

        assert onboarding_state.ready_for_completion is True

        # Test 3: No change when user_context is not ready
        onboarding_state.user_context.ready_for_orchestrator = False
        onboarding_state.ready_for_completion = False

        onboarding_state.ensure_completion_consistency()

        assert onboarding_state.ready_for_completion is False


class TestOnboardingAgent:
    """Tests for OnboardingAgent class."""

    @pytest.mark.asyncio
    async def test_onboarding_agent_initialization(self):
        """Test OnboardingAgent initialization."""
        agent = OnboardingAgent()
        assert agent is not None

    @pytest.mark.asyncio
    async def test_process_message_creates_new_state(self, onboarding_agent, sample_user_id):
        """Test process_message creates new state when none provided."""
        message = "Hello"

        response, state = await onboarding_agent.process_message(sample_user_id, message)

        assert isinstance(response, str)
        assert isinstance(state, OnboardingState)
        assert state.user_id == sample_user_id
        # When a message is sent to a new state, it should advance from PRESENTATION
        assert state.current_flow_step == FlowStep.STEP_1_CHOICE
        assert state.user_context.preferred_name == "Hello"

    @pytest.mark.asyncio
    async def test_process_message_with_existing_state(self, onboarding_agent, sample_user_id, onboarding_state):
        """Test process_message with existing state."""
        message = "Test message"
        onboarding_state.current_flow_step = FlowStep.STEP_1_CHOICE

        response, state = await onboarding_agent.process_message(sample_user_id, message, onboarding_state)

        assert isinstance(response, str)
        assert isinstance(state, OnboardingState)
        assert state.user_id == sample_user_id

    @pytest.mark.asyncio
    async def test_process_message_with_events_initial_presentation(self, onboarding_agent, sample_user_id, presentation_state):
        """Test process_message_with_events for initial presentation."""
        events = []
        states = []

        async for event, state in onboarding_agent.process_message_with_events(sample_user_id, "", presentation_state):
            events.append(event)
            states.append(state)

        # Should have multiple events: step update, token deltas, message completed, etc.
        assert len(events) > 0
        assert len(states) > 0

        # First event should be step update
        first_event = events[0]
        assert first_event is not None
        assert first_event["event"] == "step.update"
        assert first_event["data"]["status"] == "presented"
        assert first_event["data"]["step_id"] == FlowStep.PRESENTATION.value

        # Should have message completed event
        message_completed_events = [e for e in events if e and e.get("event") == "message.completed"]
        assert len(message_completed_events) == 1

        # Final state should be updated
        final_state = states[-1]
        assert final_state.current_flow_step == FlowStep.PRESENTATION
        assert final_state.last_agent_response is not None

    @pytest.mark.asyncio
    async def test_process_message_with_events_skip_flow(self, onboarding_agent, sample_user_id, onboarding_state):
        """Test process_message_with_events with skip message."""
        onboarding_state.current_flow_step = FlowStep.STEP_1_CHOICE
        onboarding_state.conversation_history = [{"turn_number": 0, "user_message": "previous", "agent_response": "response"}]

        events = []
        states = []

        async for event, state in onboarding_agent.process_message_with_events(sample_user_id, "skip", onboarding_state):
            events.append(event)
            states.append(state)

        # Should process the skip and move to next step
        assert len(events) > 0
        assert len(states) > 0

        # Check that step was completed and new step presented
        step_completed_events = [e for e in events if e and e.get("event") == "step.update" and e.get("data", {}).get("status") == "completed"]
        step_presented_events = [e for e in events if e and e.get("event") == "step.update" and e.get("data", {}).get("status") == "presented"]

        assert len(step_completed_events) >= 1
        assert len(step_presented_events) >= 1

    @pytest.mark.asyncio
    async def test_process_message_with_events_normal_flow(self, onboarding_agent, sample_user_id, onboarding_state):
        """Test process_message_with_events with normal message processing."""
        onboarding_state.current_flow_step = FlowStep.STEP_1_CHOICE
        onboarding_state.conversation_history = [{"turn_number": 0, "user_message": "previous", "agent_response": "response"}]

        events = []
        states = []

        async for event, state in onboarding_agent.process_message_with_events(sample_user_id, "answer questions", onboarding_state):
            events.append(event)
            states.append(state)

        # Should process the message and generate response
        assert len(events) > 0
        assert len(states) > 0

        # Should have validating, message completed events
        validating_events = [e for e in events if e and e.get("event") == "step.update" and e.get("data", {}).get("status") == "validating"]
        message_events = [e for e in events if e and e.get("event") == "message.completed"]

        assert len(validating_events) >= 1
        assert len(message_events) >= 1

    @pytest.mark.asyncio
    @patch('app.agents.onboarding.flow_definitions.get_llm_client')
    async def test_process_message_with_events_completion(self, mock_get_llm_client, onboarding_agent, sample_user_id):
        """Test process_message_with_events when onboarding reaches completion."""
        # Mock LLM client to avoid real calls
        mock_llm = mock_get_llm_client.return_value
        mock_llm.extract.return_value = None

        # Create a state that's about to complete (STEP_DOB_QUICK with valid age)
        from app.agents.onboarding.state import OnboardingState
        from app.agents.onboarding.types import FlowStep

        state = OnboardingState(user_id=sample_user_id)
        state.current_flow_step = FlowStep.STEP_DOB_QUICK
        state.user_context.age = 25  # Valid age
        state.user_context.preferred_name = "Test User"
        # Add a conversation turn that doesn't contain "open" to avoid SUBSCRIPTION_NOTICE
        state.add_conversation_turn("Hello", "Welcome!")

        events = []
        states = []

        async for event, current_state in onboarding_agent.process_message_with_events(sample_user_id, "1990-01-01", state):
            events.append(event)
            states.append(current_state)

        # Should emit completion event
        completion_events = [e for e in events if e and e.get("event") == "onboarding.status" and e.get("data", {}).get("status") == "done"]
        assert len(completion_events) >= 1

        # Final state should be marked as ready for completion
        final_state = states[-1]
        assert final_state.ready_for_completion is True
        assert final_state.user_context.ready_for_orchestrator is True

    @pytest.mark.asyncio
    @patch('app.agents.onboarding.flow_definitions.get_llm_client')
    async def test_process_message_with_events_step_transition_streaming(self, mock_get_llm_client, onboarding_agent, sample_user_id):
        """Test process_message_with_events with step transition and token streaming."""
        # Mock LLM client to avoid real calls
        mock_llm = mock_get_llm_client.return_value
        mock_llm.extract.return_value = None

        # Start from STEP_1_CHOICE and provide an answer that moves to STEP_2_DOB
        from app.agents.onboarding.state import OnboardingState
        from app.agents.onboarding.types import FlowStep

        state = OnboardingState(user_id=sample_user_id)
        state.current_flow_step = FlowStep.STEP_1_CHOICE
        state.user_context.preferred_name = "Test User"

        events = []
        states = []

        async for event, current_state in onboarding_agent.process_message_with_events(sample_user_id, "answer questions", state):
            events.append(event)
            states.append(current_state)

        # Should have step transition events
        step_events = [e for e in events if e and e.get("event") == "step.update"]
        assert len(step_events) >= 2  # completed + presented

        # Should have token delta events (streaming)
        token_events = [e for e in events if e and e.get("event") == "token.delta"]
        assert len(token_events) > 0

        # Should have message completed event
        message_events = [e for e in events if e and e.get("event") == "message.completed"]
        assert len(message_events) >= 1

        # Should have interaction update event (STEP_2_DOB is FREE_TEXT, so no interaction update)
        interaction_events = [e for e in events if e and e.get("event") == "interaction.update"]
        assert len(interaction_events) == 0
