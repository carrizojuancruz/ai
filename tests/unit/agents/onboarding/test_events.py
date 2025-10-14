"""Unit tests for onboarding events."""

from app.agents.onboarding.events import (
    build_interaction_update,
    emit_message_completed,
    emit_onboarding_done,
    emit_step_update,
    emit_token_delta,
)
from app.agents.onboarding.types import FlowStep, InteractionType


class TestEmitEvents:
    """Tests for event emission functions."""

    def test_emit_step_update_with_valid_step(self):
        """Test emit_step_update with a valid step."""
        event = emit_step_update("presented", FlowStep.STEP_1_CHOICE.value)

        assert event["event"] == "step.update"
        assert event["data"]["status"] == "presented"
        assert event["data"]["step_id"] == FlowStep.STEP_1_CHOICE.value
        assert event["data"]["step_index"] == 0

    def test_emit_step_update_with_invalid_step(self):
        """Test emit_step_update with an invalid step."""
        event = emit_step_update("completed", "invalid_step")

        assert event["event"] == "step.update"
        assert event["data"]["status"] == "completed"
        assert event["data"]["step_id"] == "invalid_step"
        # Should not have step_index for invalid step
        assert "step_index" not in event["data"]

    def test_emit_token_delta(self):
        """Test emit_token_delta."""
        text = "Hello world"
        event = emit_token_delta(text)

        assert event["event"] == "token.delta"
        assert event["data"]["text"] == text

    def test_emit_message_completed(self):
        """Test emit_message_completed."""
        text = "This is a complete message."
        event = emit_message_completed(text)

        assert event["event"] == "message.completed"
        assert event["data"]["text"] == text

    def test_emit_onboarding_done(self):
        """Test emit_onboarding_done."""
        event = emit_onboarding_done()

        assert event["event"] == "onboarding.status"
        assert event["data"]["status"] == "done"


class TestBuildInteractionUpdate:
    """Tests for build_interaction_update function."""

    def test_build_interaction_update_free_text(self, onboarding_state):
        """Test build_interaction_update returns None for free text."""
        onboarding_state.current_interaction_type = InteractionType.FREE_TEXT

        result = build_interaction_update(onboarding_state)

        assert result is None

    def test_build_interaction_update_single_choice(self, onboarding_state):
        """Test build_interaction_update for single choice interaction."""
        from app.agents.onboarding.types import Choice

        onboarding_state.current_interaction_type = InteractionType.SINGLE_CHOICE
        onboarding_state.current_flow_step = FlowStep.STEP_1_CHOICE
        onboarding_state.current_choices = [
            Choice(id="choice1", label="Choice 1", value="value1", synonyms=["opt1"]),
            Choice(id="choice2", label="Choice 2", value="value2", synonyms=["opt2"])
        ]

        result = build_interaction_update(onboarding_state)

        assert result is not None
        assert result["event"] == "interaction.update"
        assert result["data"]["type"] == InteractionType.SINGLE_CHOICE.value
        assert result["data"]["step_id"] == FlowStep.STEP_1_CHOICE.value
        assert "choices" in result["data"]

    def test_build_interaction_update_multi_choice(self, onboarding_state):
        """Test build_interaction_update for multi choice interaction."""
        onboarding_state.current_interaction_type = InteractionType.MULTI_CHOICE
        onboarding_state.current_flow_step = FlowStep.STEP_4_HOUSING

        result = build_interaction_update(onboarding_state)

        assert result is not None
        assert result["event"] == "interaction.update"
        assert result["data"]["type"] == InteractionType.MULTI_CHOICE.value
        assert result["data"]["step_id"] == FlowStep.STEP_4_HOUSING.value
