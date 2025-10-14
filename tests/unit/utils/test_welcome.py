"""
Unit tests for app.utils.welcome module.

Tests cover:
- User context formatting for prompts
- Personalized welcome message generation
- LLM calling with guardrails
- Guardrail text detection and placeholder conversion
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.utils.welcome import (
    _format_user_context_for_prompt,
    _is_guardrail_text,
    _to_guardrail_placeholder,
    call_llm,
    generate_personalized_welcome,
)


class TestFormatUserContextForPrompt:
    """Test _format_user_context_for_prompt function."""

    def test_format_user_context_complete(self):
        """Test formatting with all fields present."""
        user_context = {
            "identity": {"preferred_name": "John"},
            "tone": "professional",
            "locale": "en-US",
            "goals": ["save money", "invest", "retire early"]
        }

        result = _format_user_context_for_prompt(user_context)
        expected = "name=John; tone=professional; locale=en-US; goals=save money, invest, retire early"
        assert result == expected

    def test_format_user_context_minimal(self):
        """Test formatting with minimal fields."""
        user_context = {}

        result = _format_user_context_for_prompt(user_context)
        expected = "name=there; tone=friendly; locale=en-US; goals="
        assert result == expected

    def test_format_user_context_alternate_name(self):
        """Test formatting with preferred_name at root level."""
        user_context = {
            "preferred_name": "Jane",
            "tone": "casual"
        }

        result = _format_user_context_for_prompt(user_context)
        expected = "name=Jane; tone=casual; locale=en-US; goals="
        assert result == expected

    def test_format_user_context_empty_goals(self):
        """Test formatting with empty goals list."""
        user_context = {
            "identity": {"preferred_name": "Bob"},
            "goals": []
        }

        result = _format_user_context_for_prompt(user_context)
        expected = "name=Bob; tone=friendly; locale=en-US; goals="
        assert result == expected

    def test_format_user_context_non_list_goals(self):
        """Test formatting with non-list goals."""
        user_context = {
            "identity": {"preferred_name": "Alice"},
            "goals": "save money"  # String instead of list
        }

        result = _format_user_context_for_prompt(user_context)
        expected = "name=Alice; tone=friendly; locale=en-US; goals="
        assert result == expected

    def test_format_user_context_limit_goals(self):
        """Test that goals are limited to first 3."""
        user_context = {
            "identity": {"preferred_name": "Charlie"},
            "goals": ["goal1", "goal2", "goal3", "goal4", "goal5"]
        }

        result = _format_user_context_for_prompt(user_context)
        expected = "name=Charlie; tone=friendly; locale=en-US; goals=goal1, goal2, goal3"
        assert result == expected


class TestGeneratePersonalizedWelcome:
    """Test generate_personalized_welcome function."""

    @pytest.mark.asyncio
    async def test_generate_personalized_welcome_success(self):
        """Test successful welcome generation with LLM."""
        user_context = {
            "identity": {"preferred_name": "John"},
            "tone": "friendly",
            "locale": "en-US"
        }

        mock_msg = MagicMock()
        mock_msg.content = "Welcome John! Ready to help with your finances."

        mock_chat = MagicMock()
        mock_chat.ainvoke = AsyncMock(return_value=mock_msg)

        with patch("app.utils.welcome.config") as mock_config, \
             patch("app.utils.welcome.ChatBedrock", return_value=mock_chat) as mock_bedrock:

            mock_config.get_aws_region.return_value = "us-east-1"
            mock_config.BEDROCK_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"

            result = await generate_personalized_welcome(user_context)

            assert result == "Welcome John! Ready to help with your finances."
            mock_bedrock.assert_called_once()
            mock_chat.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_personalized_welcome_with_prior_summary_dict(self):
        """Test welcome generation with prior summary as dict."""
        user_context = {"identity": {"preferred_name": "Jane"}}
        prior_summary = {"short_one_liner": "We discussed investment options"}

        mock_msg = MagicMock()
        mock_msg.content = "Welcome back Jane! Shall we continue discussing investments?"

        mock_chat = MagicMock()
        mock_chat.ainvoke = AsyncMock(return_value=mock_msg)

        with patch("app.utils.welcome.config") as mock_config, \
             patch("app.utils.welcome.ChatBedrock", return_value=mock_chat):

            mock_config.get_aws_region.return_value = "us-east-1"
            mock_config.BEDROCK_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"

            result = await generate_personalized_welcome(user_context, prior_summary)

            assert result == "Welcome back Jane! Shall we continue discussing investments?"
            # Verify the prompt includes the prior summary
            call_args = mock_chat.ainvoke.call_args[0][0]
            human_content = call_args[1].content
            assert "Last conversation: We discussed investment options." in human_content

    @pytest.mark.asyncio
    async def test_generate_personalized_welcome_with_prior_summary_string(self):
        """Test welcome generation with prior summary as string."""
        user_context = {"identity": {"preferred_name": "Bob"}}
        prior_summary = "Previous chat about savings"

        mock_msg = MagicMock()
        mock_msg.content = "Hi Bob! Let's continue our savings discussion."

        mock_chat = MagicMock()
        mock_chat.ainvoke = AsyncMock(return_value=mock_msg)

        with patch("app.utils.welcome.config") as mock_config, \
             patch("app.utils.welcome.ChatBedrock", return_value=mock_chat):

            mock_config.get_aws_region.return_value = "us-east-1"
            mock_config.BEDROCK_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"

            result = await generate_personalized_welcome(user_context, prior_summary)

            assert result == "Hi Bob! Let's continue our savings discussion."
            call_args = mock_chat.ainvoke.call_args[0][0]
            human_content = call_args[1].content
            assert "Last conversation: Previous chat about savings." in human_content

    @pytest.mark.asyncio
    async def test_generate_personalized_welcome_with_icebreaker(self):
        """Test welcome generation with icebreaker hint."""
        user_context = {"identity": {"preferred_name": "Alice"}}
        icebreaker_hint = "You mentioned wanting to start investing"

        mock_msg = MagicMock()
        mock_msg.content = "Hello Alice! Since you wanted to start investing, how can I help?"

        mock_chat = MagicMock()
        mock_chat.ainvoke = AsyncMock(return_value=mock_msg)

        with patch("app.utils.welcome.config") as mock_config, \
             patch("app.utils.welcome.ChatBedrock", return_value=mock_chat):

            mock_config.get_aws_region.return_value = "us-east-1"
            mock_config.BEDROCK_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"

            result = await generate_personalized_welcome(user_context, None, icebreaker_hint)

            assert result == "Hello Alice! Since you wanted to start investing, how can I help?"
            call_args = mock_chat.ainvoke.call_args[0][0]
            human_content = call_args[1].content
            assert "Icebreaker hint: You mentioned wanting to start investing." in human_content


class TestCallLlm:
    """Test call_llm function."""

    @pytest.mark.asyncio
    async def test_call_llm_success_with_system(self):
        """Test successful LLM call with system message."""
        system = "You are a helpful assistant."
        prompt = "Hello, how are you?"

        mock_msg = MagicMock()
        mock_msg.content = "I'm doing well, thank you!"

        mock_chat = MagicMock()
        mock_chat.ainvoke = AsyncMock(return_value=mock_msg)

        with patch("app.utils.welcome.config") as mock_config, \
             patch("app.utils.welcome.ChatBedrock", return_value=mock_chat):

            mock_config.SUPERVISOR_AGENT_MODEL_REGION = "us-east-1"
            mock_config.SUPERVISOR_AGENT_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"
            mock_config.SUPERVISOR_AGENT_GUARDRAIL_ID = "test-guardrail"
            mock_config.SUPERVISOR_AGENT_GUARDRAIL_VERSION = "1"

            result = await call_llm(system, prompt)

            assert result == "I'm doing well, thank you!"
            mock_chat.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_llm_success_without_system(self):
        """Test successful LLM call without system message."""
        system = None
        prompt = "Tell me a joke."

        mock_msg = MagicMock()
        mock_msg.content = "Why did the chicken cross the road? To get to the other side!"

        mock_chat = MagicMock()
        mock_chat.ainvoke = AsyncMock(return_value=mock_msg)

        with patch("app.utils.welcome.config") as mock_config, \
             patch("app.utils.welcome.ChatBedrock", return_value=mock_chat):

            mock_config.SUPERVISOR_AGENT_MODEL_REGION = "us-east-1"
            mock_config.SUPERVISOR_AGENT_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"
            mock_config.SUPERVISOR_AGENT_GUARDRAIL_ID = None
            mock_config.SUPERVISOR_AGENT_GUARDRAIL_VERSION = None

            result = await call_llm(system, prompt)

            assert result == "Why did the chicken cross the road? To get to the other side!"
            # Verify only HumanMessage is sent when no system message

    @pytest.mark.asyncio
    async def test_call_llm_with_reasoning_removal(self):
        """Test that reasoning tags are removed from response."""
        system = "You are a helpful assistant."
        prompt = "Explain quantum physics."

        mock_msg = MagicMock()
        mock_msg.content = "<reasoning>Let me think about this...</reasoning>Quantum physics is complex."

        mock_chat = MagicMock()
        mock_chat.ainvoke = AsyncMock(return_value=mock_msg)

        with patch("app.utils.welcome.config") as mock_config, \
             patch("app.utils.welcome.ChatBedrock", return_value=mock_chat):

            mock_config.SUPERVISOR_AGENT_MODEL_REGION = "us-east-1"
            mock_config.SUPERVISOR_AGENT_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"
            mock_config.SUPERVISOR_AGENT_GUARDRAIL_ID = None
            mock_config.SUPERVISOR_AGENT_GUARDRAIL_VERSION = None

            result = await call_llm(system, prompt)

            assert result == "Quantum physics is complex."

    @pytest.mark.asyncio
    async def test_call_llm_guardrail_intervention(self):
        """Test guardrail intervention detection and placeholder."""
        system = "You are a helpful assistant."
        prompt = "Some inappropriate content"

        mock_msg = MagicMock()
        mock_msg.content = "GUARDRAIL_INTERVENED: GR_INPUT_BLOCKED"

        mock_chat = MagicMock()
        mock_chat.ainvoke = AsyncMock(return_value=mock_msg)

        with patch("app.utils.welcome.config") as mock_config, \
             patch("app.utils.welcome.ChatBedrock", return_value=mock_chat):

            mock_config.SUPERVISOR_AGENT_MODEL_REGION = "us-east-1"
            mock_config.SUPERVISOR_AGENT_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"
            mock_config.SUPERVISOR_AGENT_GUARDRAIL_ID = "test-guardrail"
            mock_config.SUPERVISOR_AGENT_GUARDRAIL_VERSION = "1"

            result = await call_llm(system, prompt)

            assert result == '[GUARDRAIL_INTERVENED] {"code":"GR_INPUT_BLOCKED"}'

    @pytest.mark.asyncio
    async def test_call_llm_no_region_fallback(self):
        """Test fallback when no region is configured."""
        system = "You are a helpful assistant."
        prompt = "Hello world"

        with patch("app.utils.welcome.config") as mock_config:
            mock_config.SUPERVISOR_AGENT_MODEL_REGION = None
            mock_config.SUPERVISOR_AGENT_MODEL_ID = "test-model"
            mock_config.SUPERVISOR_AGENT_GUARDRAIL_ID = None
            mock_config.SUPERVISOR_AGENT_GUARDRAIL_VERSION = None

            result = await call_llm(system, prompt)

            assert result == "Hello world"

    @pytest.mark.asyncio
    async def test_call_llm_exception_fallback(self):
        """Test fallback when LLM call raises exception."""
        system = "You are a helpful assistant."
        prompt = "Hello"

        mock_chat = MagicMock()
        mock_chat.ainvoke = AsyncMock(side_effect=Exception("Network error"))

        with patch("app.utils.welcome.config") as mock_config, \
             patch("app.utils.welcome.ChatBedrock", return_value=mock_chat):

            mock_config.SUPERVISOR_AGENT_MODEL_REGION = "us-east-1"
            mock_config.SUPERVISOR_AGENT_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"
            mock_config.SUPERVISOR_AGENT_GUARDRAIL_ID = None
            mock_config.SUPERVISOR_AGENT_GUARDRAIL_VERSION = None

            result = await call_llm(system, prompt)

            assert result == ""


class TestIsGuardrailText:
    """Test _is_guardrail_text function."""

    def test_is_guardrail_text_guardrail_intervened(self):
        """Test detection of GUARDRAIL_INTERVENED."""
        text = "GUARDRAIL_INTERVENED: Content blocked"
        assert _is_guardrail_text(text) is True

    def test_is_guardrail_text_gr_input_blocked(self):
        """Test detection of GR_INPUT_BLOCKED."""
        text = "gr_input_blocked - inappropriate content"
        assert _is_guardrail_text(text) is True

    def test_is_guardrail_text_guardrail_blocked(self):
        """Test detection of guardrail blocked."""
        text = "Content guardrail blocked due to policy"
        assert _is_guardrail_text(text) is True

    def test_is_guardrail_text_guardrail_intervened_combined(self):
        """Test detection of guardrail intervened."""
        text = "The guardrail intervened and blocked this request"
        assert _is_guardrail_text(text) is True

    def test_is_guardrail_text_normal_text(self):
        """Test that normal text is not detected as guardrail."""
        text = "This is a normal response from the assistant."
        assert _is_guardrail_text(text) is False

    def test_is_guardrail_text_empty_string(self):
        """Test empty string."""
        text = ""
        assert _is_guardrail_text(text) is False

    def test_is_guardrail_text_non_string(self):
        """Test non-string input."""
        text = None
        assert _is_guardrail_text(text) is False


class TestToGuardrailPlaceholder:
    """Test _to_guardrail_placeholder function."""

    def test_to_guardrail_placeholder_gr_input_blocked(self):
        """Test placeholder for GR_INPUT_BLOCKED."""
        text = "GUARDRAIL_INTERVENED: GR_INPUT_BLOCKED - inappropriate content"
        result = _to_guardrail_placeholder(text)
        assert result == '[GUARDRAIL_INTERVENED] {"code":"GR_INPUT_BLOCKED"}'

    def test_to_guardrail_placeholder_unknown(self):
        """Test placeholder for unknown guardrail code."""
        text = "GUARDRAIL_INTERVENED: Some other reason"
        result = _to_guardrail_placeholder(text)
        assert result == '[GUARDRAIL_INTERVENED] {"code":"UNKNOWN"}'

    def test_to_guardrail_placeholder_case_insensitive(self):
        """Test case insensitive detection."""
        text = "guardrail_intervened: gr_input_blocked"
        result = _to_guardrail_placeholder(text)
        assert result == '[GUARDRAIL_INTERVENED] {"code":"UNKNOWN"}'
