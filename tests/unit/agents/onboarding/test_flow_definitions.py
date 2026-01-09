"""Unit tests for onboarding flow definitions."""
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.agents.onboarding.flow_definitions import (
    determine_next_step,
    get_current_step_definition,
    process_user_response,
    validate_dob,
    validate_housing_cost,
    validate_location,
    validate_name,
)
from app.agents.onboarding.types import FlowStep, InteractionType


class TestGetCurrentStepDefinition:
    """Tests for get_current_step_definition function."""

    def test_get_current_step_definition_presentation(self, onboarding_state):
        """Test getting step definition for presentation step."""
        onboarding_state.current_flow_step = FlowStep.PRESENTATION

        step_def = get_current_step_definition(onboarding_state)

        assert step_def.id == FlowStep.PRESENTATION
        assert step_def.interaction_type == InteractionType.FREE_TEXT

    def test_get_current_step_definition_step_1_choice(self, onboarding_state):
        """Test getting step definition for step 1 choice."""
        onboarding_state.current_flow_step = FlowStep.STEP_1_CHOICE

        step_def = get_current_step_definition(onboarding_state)

        assert step_def.id == FlowStep.STEP_1_CHOICE
        assert step_def.interaction_type == InteractionType.SINGLE_CHOICE
        assert len(step_def.choices) == 2  # Should have 2 choices

    def test_get_current_step_definition_unknown_step(self, onboarding_state):
        """Test getting step definition for unknown step falls back to presentation."""
        # Create a mock step that's not in FLOW_DEFINITIONS
        onboarding_state.current_flow_step = "unknown_step"  # type: ignore

        step_def = get_current_step_definition(onboarding_state)

        # Should fall back to presentation
        assert step_def.id == FlowStep.PRESENTATION


class TestDetermineNextStep:
    """Tests for determine_next_step function."""

    def test_determine_next_step_from_presentation_with_name(self, onboarding_state):
        """Test next step from presentation when user provides name."""
        onboarding_state.current_flow_step = FlowStep.PRESENTATION
        response = "John"

        next_step = determine_next_step(response, onboarding_state)

        assert next_step == FlowStep.STEP_1_CHOICE
        assert onboarding_state.user_context.preferred_name == "John"

    def test_determine_next_step_from_presentation_without_name(self, onboarding_state):
        """Test next step from presentation when no name provided."""
        onboarding_state.current_flow_step = FlowStep.PRESENTATION
        response = ""

        next_step = determine_next_step(response, onboarding_state)

        assert next_step == FlowStep.PRESENTATION

    def test_determine_next_step_from_step_1_choice_skip(self, onboarding_state):
        """Test next step from step 1 choice when user wants to skip."""
        onboarding_state.current_flow_step = FlowStep.STEP_1_CHOICE

        test_responses = ["skip", "open chat", "no questions", "Skip"]
        for response in test_responses:
            next_step = determine_next_step(response, onboarding_state)
            assert next_step == FlowStep.STEP_DOB_QUICK

    def test_determine_next_step_from_step_1_choice_answer(self, onboarding_state):
        """Test next step from step 1 choice when user wants to answer questions."""
        onboarding_state.current_flow_step = FlowStep.STEP_1_CHOICE
        response = "answer questions"

        next_step = determine_next_step(response, onboarding_state)

        assert next_step == FlowStep.STEP_2_DOB

    def test_determine_next_step_from_dob_quick_under_18(self, onboarding_state):
        """Test next step from DOB quick when user is under 18."""
        onboarding_state.current_flow_step = FlowStep.STEP_DOB_QUICK
        onboarding_state.user_context.age = 16

        next_step = determine_next_step("16", onboarding_state)

        assert next_step == FlowStep.TERMINATED_UNDER_18

    def test_determine_next_step_from_dob_quick_adult_complete(self, onboarding_state):
        """Test next step from DOB quick when user is adult and completes."""
        onboarding_state.current_flow_step = FlowStep.STEP_DOB_QUICK
        onboarding_state.user_context.age = 25

        next_step = determine_next_step("25", onboarding_state)

        assert next_step == FlowStep.COMPLETE
        assert onboarding_state.ready_for_completion is True


class TestProcessUserResponse:
    """Tests for process_user_response function."""

    def test_process_user_response_validation_failure(self, onboarding_state):
        """Test process_user_response when validation fails."""
        onboarding_state.current_flow_step = FlowStep.STEP_2_DOB
        invalid_response = "invalid date"

        response_text, next_step, interaction_type, choices = process_user_response(onboarding_state, invalid_response)

        # Should return error message and stay on same step
        assert "valid date format" in response_text
        assert next_step == FlowStep.STEP_2_DOB
        assert interaction_type == InteractionType.FREE_TEXT

    def test_process_user_response_validation_success(self, onboarding_state):
        """Test process_user_response when validation succeeds."""
        onboarding_state.current_flow_step = FlowStep.STEP_2_DOB
        valid_response = "1990-01-01"

        response_text, next_step, interaction_type, choices = process_user_response(onboarding_state, valid_response)

        # Should advance to next step
        assert next_step == FlowStep.STEP_3_LOCATION
        assert interaction_type == InteractionType.FREE_TEXT

    def test_process_user_response_no_next_step(self, onboarding_state):
        """Test process_user_response when there's no next step defined."""
        onboarding_state.current_flow_step = FlowStep.COMPLETE

        response_text, next_step, interaction_type, choices = process_user_response(onboarding_state, "test")

        # Should return default message
        assert response_text == "Thanks for chatting with me!"
        assert next_step is None
        assert interaction_type == InteractionType.FREE_TEXT
        assert choices == []

    def test_process_user_response_with_callable_next_step(self, onboarding_state):
        """Test process_user_response with callable next_step."""
        from app.agents.onboarding.flow_definitions import FLOW_DEFINITIONS

        # Mock the validation function in the step definition
        mock_validate = MagicMock(return_value=(True, None))
        original_validate = FLOW_DEFINITIONS[FlowStep.STEP_3_LOCATION].validation
        FLOW_DEFINITIONS[FlowStep.STEP_3_LOCATION].validation = mock_validate

        try:
            onboarding_state.current_flow_step = FlowStep.STEP_3_LOCATION
            response = "New York, NY"

            response_text, next_step, interaction_type, choices = process_user_response(onboarding_state, response)

            # Should call validation and advance
            mock_validate.assert_called_once_with(response, onboarding_state)
            assert next_step == FlowStep.STEP_4_HOUSING
        finally:
            # Restore original validation function
            FLOW_DEFINITIONS[FlowStep.STEP_3_LOCATION].validation = original_validate


class TestValidateName:
    """Tests for validate_name function."""

    @patch('app.agents.onboarding.flow_definitions.BedrockLLM')
    def test_validate_name_empty_response(self, mock_bedrock_class, onboarding_state):
        """Test validate_name with empty response."""
        is_valid, error_msg = validate_name("", onboarding_state)
        assert is_valid is False
        assert "Please tell me what you'd like to be called." in error_msg
        mock_bedrock_class.assert_not_called()

    @patch('app.agents.onboarding.flow_definitions.BedrockLLM')
    def test_validate_name_single_word(self, mock_bedrock_class, onboarding_state):
        """Test validate_name with single word (LLM is called but returns None, falls back to tokenization)."""
        mock_llm = MagicMock()
        mock_llm.extract.return_value = {"preferred_name": None}
        mock_bedrock_class.return_value = mock_llm

        is_valid, error_msg = validate_name("John", onboarding_state)
        assert is_valid is True
        assert error_msg is None
        assert onboarding_state.user_context.preferred_name == "John"
        mock_bedrock_class.assert_called_once()

    @patch('app.agents.onboarding.flow_definitions.BedrockLLM')
    def test_validate_name_llm_success(self, mock_bedrock_class, onboarding_state):
        """Test validate_name with LLM extraction success."""
        mock_llm = MagicMock()
        mock_llm.extract.return_value = {"preferred_name": "Jane Doe"}
        mock_bedrock_class.return_value = mock_llm

        is_valid, error_msg = validate_name("My name is Jane", onboarding_state)
        assert is_valid is True
        assert error_msg is None
        assert onboarding_state.user_context.preferred_name == "Jane Doe"
        mock_bedrock_class.assert_called_once()
        mock_llm.extract.assert_called_once()

    @patch('app.agents.onboarding.flow_definitions.BedrockLLM')
    def test_validate_name_llm_failure_fallback(self, mock_bedrock_class, onboarding_state):
        """Test validate_name with LLM failure, falls back to tokenization."""
        mock_llm = MagicMock()
        mock_llm.extract.side_effect = Exception("LLM error")
        mock_bedrock_class.return_value = mock_llm

        is_valid, error_msg = validate_name("Hello I am Bob", onboarding_state)
        assert is_valid is False  # Multiple words, no single alpha word
        assert "Please tell me what you'd like to be called." in error_msg
        mock_bedrock_class.assert_called_once()

    @patch('app.agents.onboarding.flow_definitions.BedrockLLM')
    def test_validate_name_llm_returns_none(self, mock_bedrock_class, onboarding_state):
        """Test validate_name when LLM returns None."""
        mock_llm = MagicMock()
        mock_llm.extract.return_value = {"preferred_name": None}
        mock_bedrock_class.return_value = mock_llm

        is_valid, error_msg = validate_name("Some complex name", onboarding_state)
        assert is_valid is False
        assert "Please tell me what you'd like to be called." in error_msg
        mock_bedrock_class.assert_called_once()


class TestValidateDOB:
    """Tests for validate_dob function."""

    @patch('app.agents.onboarding.flow_definitions.date')
    def test_validate_dob_valid_yyyy_mm_dd(self, mock_date, onboarding_state):
        """Test validate_dob with valid YYYY-MM-DD format."""
        mock_date.today.return_value = datetime.date(2025, 6, 15)
        is_valid, error_msg = validate_dob("1990-01-15", onboarding_state)
        assert is_valid is True
        assert error_msg is None
        assert onboarding_state.user_context.age == 35  # 2025 - 1990 = 35

    @patch('app.agents.onboarding.flow_definitions.date')
    def test_validate_dob_valid_mm_dd_yyyy(self, mock_date, onboarding_state):
        """Test validate_dob with valid MM/DD/YYYY format."""
        mock_date.today.return_value = datetime.date(2025, 6, 15)
        is_valid, error_msg = validate_dob("01/15/1990", onboarding_state)
        assert is_valid is True
        assert error_msg is None

    @patch('app.agents.onboarding.flow_definitions.date')
    def test_validate_dob_under_18(self, mock_date, onboarding_state):
        """Test validate_dob with date making person under 18."""
        mock_date.today.return_value = datetime.date(2025, 6, 15)
        is_valid, error_msg = validate_dob("2010-01-01", onboarding_state)
        assert is_valid is True
        assert error_msg is None
        assert onboarding_state.user_context.age == datetime.now().year - 2010  # 2025 - 2010 = 15

    def test_validate_dob_invalid_format(self, onboarding_state):
        """Test validate_dob with invalid format."""
        is_valid, error_msg = validate_dob("not a date", onboarding_state)
        assert is_valid is False
        assert "valid date format" in error_msg

    @patch('app.agents.onboarding.flow_definitions.date')
    def test_validate_dob_future_date(self, mock_date, onboarding_state):
        """Test validate_dob with future date."""
        mock_date.today.return_value = datetime.date(2025, 6, 15)
        is_valid, error_msg = validate_dob("2030-01-01", onboarding_state)
        assert is_valid is True  # Technically valid format
        assert error_msg is None
        assert onboarding_state.user_context.age == datetime.now().year - 2030  # 2025 - 2030 = -5


class TestValidateLocation:
    """Tests for validate_location function."""

    @patch('app.agents.onboarding.flow_definitions.BedrockLLM')
    def test_validate_location_too_short(self, mock_bedrock_llm, onboarding_state):
        """Test validate_location with response too short."""
        is_valid, error_msg = validate_location("NY", onboarding_state)
        assert is_valid is False
        assert "city and state" in error_msg
        mock_bedrock_llm.assert_not_called()

    @patch('app.agents.onboarding.flow_definitions.BedrockLLM')
    def test_validate_location_comma_separated(self, mock_bedrock_llm, onboarding_state):
        """Test validate_location with comma-separated city and state."""
        is_valid, error_msg = validate_location("New York, NY", onboarding_state)
        assert is_valid is True
        assert error_msg is None
        assert onboarding_state.user_context.location.city == "New York"
        assert onboarding_state.user_context.location.region == "NY"
        mock_bedrock_llm.assert_not_called()

    @patch('app.agents.onboarding.flow_definitions.BedrockLLM')
    def test_validate_location_llm_success(self, mock_bedrock_llm, onboarding_state):
        """Test validate_location using LLM extraction."""
        mock_llm_instance = MagicMock()
        mock_llm_instance.extract.return_value = {"city": "Los Angeles", "region": "CA"}
        mock_bedrock_llm.return_value = mock_llm_instance

        is_valid, error_msg = validate_location("I live in LA", onboarding_state)
        assert is_valid is True
        assert error_msg is None
        assert onboarding_state.user_context.location.city == "Los Angeles"
        assert onboarding_state.user_context.location.region == "CA"
        mock_bedrock_llm.assert_called_once()

    @patch('app.agents.onboarding.flow_definitions.BedrockLLM')
    def test_validate_location_llm_failure_fallback(self, mock_bedrock_llm, onboarding_state):
        """Test validate_location with LLM failure, uses fallback."""
        mock_llm_instance = MagicMock()
        mock_llm_instance.extract.side_effect = Exception("LLM error")
        mock_bedrock_llm.return_value = mock_llm_instance

        is_valid, error_msg = validate_location("Chicago", onboarding_state)
        assert is_valid is True
        assert error_msg is None
        assert onboarding_state.user_context.location.city == "Chicago"
        assert onboarding_state.user_context.location.region is None
        mock_bedrock_llm.assert_called_once()


class TestValidateHousingCost:
    """Tests for validate_housing_cost function."""

    def test_validate_housing_cost_empty(self, onboarding_state):
        """Test validate_housing_cost with empty response."""
        is_valid, error_msg = validate_housing_cost("", onboarding_state)
        assert is_valid is False
        assert "monthly rent or mortgage" in error_msg

    def test_validate_housing_cost_valid(self, onboarding_state):
        """Test validate_housing_cost with valid response."""
        is_valid, error_msg = validate_housing_cost("$2000", onboarding_state)
        assert is_valid is True
        assert error_msg is None
        assert onboarding_state.user_context.rent_mortgage == "$2000"


class TestMessageFunctions:
    """Tests for callable message functions."""

    def test_get_presentation_message(self, onboarding_state):
        """Test get_presentation_message function."""
        from app.agents.onboarding.flow_definitions import get_presentation_message

        message = get_presentation_message(onboarding_state)
        assert "Hi there!" in message
        assert "Vera" in message
        assert "what should I call you?" in message

    def test_get_step_1_message_with_name(self, onboarding_state):
        """Test get_step_1_message with preferred name."""
        from app.agents.onboarding.flow_definitions import get_step_1_message

        onboarding_state.user_context.preferred_name = "Alice"
        message = get_step_1_message(onboarding_state)
        assert "Nice to meet you, Alice!" in message

    def test_get_step_1_message_without_name(self, onboarding_state):
        """Test get_step_1_message without preferred name."""
        from app.agents.onboarding.flow_definitions import get_step_1_message

        message = get_step_1_message(onboarding_state)
        assert "{Name}" in message  # Should use placeholder


class TestDetermineNextStepExtended:
    """Extended tests for determine_next_step covering more branches."""

    def test_determine_next_step_from_step_2_dob_adult_no_open_chat(self, onboarding_state):
        """Test next step from STEP_2_DOB when user is adult and no open chat."""
        onboarding_state.current_flow_step = FlowStep.STEP_2_DOB
        onboarding_state.user_context.age = 25

        next_step = determine_next_step("25", onboarding_state)
        assert next_step == FlowStep.STEP_3_LOCATION

    def test_determine_next_step_from_step_2_dob_with_open_chat(self, onboarding_state):
        """Test next step from STEP_2_DOB when conversation contains 'open'."""
        onboarding_state.current_flow_step = FlowStep.STEP_2_DOB
        onboarding_state.user_context.age = 25
        onboarding_state.conversation_history = [
            {"user_message": "I want to open chat", "agent_response": "ok"}
        ]

        next_step = determine_next_step("25", onboarding_state)
        assert next_step == FlowStep.SUBSCRIPTION_NOTICE

    def test_determine_next_step_from_step_3_location(self, onboarding_state):
        """Test next step from STEP_3_LOCATION."""
        onboarding_state.current_flow_step = FlowStep.STEP_3_LOCATION

        next_step = determine_next_step("New York, NY", onboarding_state)
        assert next_step == FlowStep.STEP_4_HOUSING

    def test_determine_next_step_from_step_4_housing(self, onboarding_state):
        """Test next step from STEP_4_HOUSING."""
        onboarding_state.current_flow_step = FlowStep.STEP_4_HOUSING

        next_step = determine_next_step("$1500", onboarding_state)
        assert next_step == FlowStep.STEP_4_MONEY_FEELINGS

    def test_determine_next_step_from_step_4_money_feelings_anxious(self, onboarding_state):
        """Test next step from STEP_4_MONEY_FEELINGS with anxious choice."""
        onboarding_state.current_flow_step = FlowStep.STEP_4_MONEY_FEELINGS

        next_step = determine_next_step("anxious", onboarding_state)
        assert next_step == FlowStep.STEP_5_INCOME_DECISION
        assert onboarding_state.user_context.money_feelings == "anxious"

    def test_determine_next_step_from_step_4_money_feelings_synonym(self, onboarding_state):
        """Test next step from STEP_4_MONEY_FEELINGS with synonym."""
        onboarding_state.current_flow_step = FlowStep.STEP_4_MONEY_FEELINGS

        next_step = determine_next_step("worried", onboarding_state)
        assert next_step == FlowStep.STEP_5_INCOME_DECISION
        assert onboarding_state.user_context.money_feelings == "anxious"

    def test_determine_next_step_from_step_5_income_decision_exact(self, onboarding_state):
        """Test next step from STEP_5_INCOME_DECISION choosing exact."""
        onboarding_state.current_flow_step = FlowStep.STEP_5_INCOME_DECISION

        next_step = determine_next_step("exact", onboarding_state)
        assert next_step == FlowStep.STEP_5_1_INCOME_EXACT

    def test_determine_next_step_from_step_5_income_decision_range(self, onboarding_state):
        """Test next step from STEP_5_INCOME_DECISION choosing range."""
        onboarding_state.current_flow_step = FlowStep.STEP_5_INCOME_DECISION

        next_step = determine_next_step("range", onboarding_state)
        assert next_step == FlowStep.STEP_5_2_INCOME_RANGE

    def test_determine_next_step_from_step_5_1_income_exact(self, onboarding_state):
        """Test next step from STEP_5_1_INCOME_EXACT."""
        onboarding_state.current_flow_step = FlowStep.STEP_5_1_INCOME_EXACT

        next_step = determine_next_step("$75000", onboarding_state)
        assert next_step == FlowStep.FINAL_WRAP_UP
        assert onboarding_state.user_context.income == "$75000"

    def test_determine_next_step_from_step_5_2_income_range_under_25k(self, onboarding_state):
        """Test next step from STEP_5_2_INCOME_RANGE choosing under 25k."""
        onboarding_state.current_flow_step = FlowStep.STEP_5_2_INCOME_RANGE

        next_step = determine_next_step("under_25k", onboarding_state)
        assert next_step == FlowStep.FINAL_WRAP_UP
        assert onboarding_state.user_context.income_band == "under_25k"

    def test_determine_next_step_from_step_5_2_income_range_synonym(self, onboarding_state):
        """Test next step from STEP_5_2_INCOME_RANGE with synonym."""
        onboarding_state.current_flow_step = FlowStep.STEP_5_2_INCOME_RANGE

        next_step = determine_next_step("low income", onboarding_state)
        assert next_step == FlowStep.FINAL_WRAP_UP
        assert onboarding_state.user_context.income_band == "under_25k"

    def test_determine_next_step_from_step_6_connect_accounts(self, onboarding_state):
        """Test next step from STEP_6_CONNECT_ACCOUNTS."""
        onboarding_state.current_flow_step = FlowStep.STEP_6_CONNECT_ACCOUNTS

        next_step = determine_next_step("connect_now", onboarding_state)
        assert next_step == FlowStep.COMPLETE
        assert onboarding_state.ready_for_completion is True

    def test_determine_next_step_unknown_step(self, onboarding_state):
        """Test determine_next_step with a step that defaults to COMPLETE."""
        # Use a valid FlowStep that's not handled in the switch (if any), or mock
        # For now, test with COMPLETE which should stay COMPLETE
        onboarding_state.current_flow_step = FlowStep.COMPLETE

        next_step = determine_next_step("test", onboarding_state)
        assert next_step == FlowStep.COMPLETE
