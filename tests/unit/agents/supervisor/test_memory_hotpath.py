from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage

from app.agents.supervisor.memory.hotpath import (
    CONTEXT_PROFILE_PREFIX,
    _collect_recent_user_texts,
    _has_existing_context_profile,
    _should_inject_profile,
)


class TestContextProfileDetection:
    def test_detects_context_profile_in_ai_message(self):
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content=f"{CONTEXT_PROFILE_PREFIX} User is 25 years old"),
        ]

        assert _has_existing_context_profile(messages) is True

    def test_ignores_context_profile_in_human_message(self):
        messages = [
            HumanMessage(content=f"{CONTEXT_PROFILE_PREFIX} User is 25 years old"),
            AIMessage(content="How can I help?"),
        ]

        assert _has_existing_context_profile(messages) is False

    def test_ignores_user_typing_context_profile(self):
        messages = [
            HumanMessage(content="CONTEXT_PROFILE: what does this mean?"),
            AIMessage(content="That's an internal marker."),
        ]

        assert _has_existing_context_profile(messages) is False

    def test_returns_false_for_empty_messages(self):
        assert _has_existing_context_profile([]) is False

    def test_returns_false_for_no_context_profile(self):
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="How can I help you today?"),
        ]

        assert _has_existing_context_profile(messages) is False

    def test_detects_context_profile_with_mock_message(self):
        mock_ai_message = MagicMock()
        mock_ai_message.type = "ai"
        mock_ai_message.content = f"{CONTEXT_PROFILE_PREFIX} User data"

        mock_human_message = MagicMock()
        mock_human_message.type = "human"
        mock_human_message.content = "Hello"

        messages = [mock_human_message, mock_ai_message]

        assert _has_existing_context_profile(messages) is True

    def test_handles_assistant_role(self):
        mock_message = MagicMock()
        mock_message.type = "assistant"
        mock_message.content = f"{CONTEXT_PROFILE_PREFIX} User data"

        assert _has_existing_context_profile([mock_message]) is True

    def test_handles_AIMessage_type_string(self):
        mock_message = MagicMock()
        mock_message.type = "AIMessage"
        mock_message.content = f"{CONTEXT_PROFILE_PREFIX} User data"

        assert _has_existing_context_profile([mock_message]) is True

    def test_ignores_user_role(self):
        mock_message = MagicMock()
        mock_message.type = "user"
        mock_message.content = f"{CONTEXT_PROFILE_PREFIX} User data"

        assert _has_existing_context_profile([mock_message]) is False

    def test_ignores_human_role(self):
        mock_message = MagicMock()
        mock_message.type = "human"
        mock_message.content = f"{CONTEXT_PROFILE_PREFIX} User data"

        assert _has_existing_context_profile([mock_message]) is False


class TestShouldInjectProfile:
    def test_inject_on_first_message(self):
        messages = [HumanMessage(content="Hello")]

        assert _should_inject_profile(messages, user_context_changed=False) is True

    def test_inject_when_context_changed(self):
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content=f"{CONTEXT_PROFILE_PREFIX} Old profile"),
        ]

        assert _should_inject_profile(messages, user_context_changed=True) is True

    def test_skip_when_profile_exists_and_no_change(self):
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content=f"{CONTEXT_PROFILE_PREFIX} Current profile"),
        ]

        assert _should_inject_profile(messages, user_context_changed=False) is False

    def test_empty_messages_triggers_injection(self):
        assert _should_inject_profile([], user_context_changed=False) is True


class TestCollectRecentUserTexts:
    def test_collects_user_messages(self):
        messages = [
            HumanMessage(content="First message"),
            AIMessage(content="Response"),
            HumanMessage(content="Second message"),
        ]

        result = _collect_recent_user_texts(messages, max_messages=3)

        assert len(result) == 2
        assert "First message" in result
        assert "Second message" in result

    def test_respects_max_messages_limit(self):
        messages = [
            HumanMessage(content="Message 1"),
            HumanMessage(content="Message 2"),
            HumanMessage(content="Message 3"),
            HumanMessage(content="Message 4"),
        ]

        result = _collect_recent_user_texts(messages, max_messages=2)

        assert len(result) == 2
        assert "Message 3" in result
        assert "Message 4" in result

    def test_handles_empty_messages(self):
        result = _collect_recent_user_texts([], max_messages=3)
        assert result == []

    def test_handles_no_user_messages(self):
        messages = [
            AIMessage(content="Hello"),
            AIMessage(content="How are you?"),
        ]

        result = _collect_recent_user_texts(messages, max_messages=3)
        assert result == []

    def test_skips_empty_content(self):
        messages = [
            HumanMessage(content="Valid message"),
            HumanMessage(content=""),
            HumanMessage(content="   "),
        ]

        result = _collect_recent_user_texts(messages, max_messages=3)

        assert len(result) == 1
        assert result[0] == "Valid message"

    def test_handles_mock_messages_with_role_attribute(self):
        mock_msg = MagicMock()
        mock_msg.role = "user"
        mock_msg.type = None
        mock_msg.content = "User message"

        result = _collect_recent_user_texts([mock_msg], max_messages=3)

        assert len(result) == 1
        assert result[0] == "User message"

    def test_handles_mock_messages_with_human_role(self):
        mock_msg = MagicMock()
        mock_msg.role = "human"
        mock_msg.type = None
        mock_msg.content = "Human message"

        result = _collect_recent_user_texts([mock_msg], max_messages=3)

        assert len(result) == 1
        assert result[0] == "Human message"
