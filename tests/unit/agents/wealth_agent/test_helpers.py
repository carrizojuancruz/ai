"""Tests for app/agents/supervisor/wealth_agent/helpers.py"""

from uuid import UUID, uuid4

import pytest
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from app.agents.supervisor.wealth_agent.helpers import (
    create_error_command,
    extract_text_from_content,
    get_last_user_message_text,
    get_user_id_from_messages,
)


@pytest.mark.unit
class TestExtractTextFromContent:
    """Test suite for extract_text_from_content function."""

    def test_extract_from_string(self):
        """Test extraction from plain string."""
        content = "This is a test message"
        result = extract_text_from_content(content)
        assert result == "This is a test message"

    def test_extract_from_list_with_dicts(self):
        """Test extraction from list of dicts with text/content keys."""
        content = [
            {"text": "First part"},
            {"content": "Second part"},
            {"text": "Third part"},
        ]
        result = extract_text_from_content(content)
        assert result == "First part\nSecond part\nThird part"

    def test_extract_from_empty_list(self):
        """Test extraction from empty list."""
        content = []
        result = extract_text_from_content(content)
        assert result == ""

    def test_extract_from_none(self):
        """Test extraction from None."""
        content = None
        result = extract_text_from_content(content)
        assert result == ""

    def test_extract_from_mixed_list(self):
        """Test extraction from list with mixed content."""
        content = [
            {"text": "Valid text"},
            {"other_key": "Ignored"},
            {"content": "Valid content"},
        ]
        result = extract_text_from_content(content)
        assert "Valid text" in result
        assert "Valid content" in result
        assert "Ignored" not in result


@pytest.mark.unit
class TestGetLastUserMessageText:
    """Test suite for get_last_user_message_text function."""

    def test_extract_from_human_message(self):
        """Test extraction from HumanMessage."""
        messages = [
            HumanMessage(content="First message"),
            HumanMessage(content="Last message"),
        ]
        result = get_last_user_message_text(messages)
        assert result == "Last message"

    def test_extract_from_dict_message(self):
        """Test extraction from dict with role=user."""
        messages = [
            {"role": "user", "content": "User message"},
            {"role": "assistant", "content": "AI response"},
        ]
        result = get_last_user_message_text(messages)
        assert result == "User message"

    def test_extract_from_mixed_messages(self):
        """Test extraction from mixed message types."""
        messages = [
            HumanMessage(content="First human"),
            {"role": "assistant", "content": "AI response"},
            {"role": "user", "content": "Last user dict"},
        ]
        result = get_last_user_message_text(messages)
        assert result == "Last user dict"

    def test_extract_from_empty_messages(self):
        """Test extraction from empty message list."""
        messages = []
        result = get_last_user_message_text(messages)
        assert result == ""

    def test_extract_with_complex_content(self):
        """Test extraction with complex content structure."""
        messages = [
            HumanMessage(content=[{"text": "Complex"}, {"text": "Content"}]),
        ]
        result = get_last_user_message_text(messages)
        assert "Complex" in result
        assert "Content" in result


@pytest.mark.unit
class TestGetUserIdFromMessages:
    """Test suite for get_user_id_from_messages function."""

    def test_extract_user_id_from_dict(self):
        """Test extraction of user_id from dict message."""
        user_id = uuid4()
        messages = [
            {"role": "user", "content": "Test", "user_id": str(user_id)},
        ]
        result = get_user_id_from_messages(messages)
        assert isinstance(result, UUID)
        assert result == user_id

    def test_extract_user_id_as_uuid(self):
        """Test extraction when user_id is already UUID."""
        user_id = uuid4()
        messages = [
            {"role": "user", "content": "Test", "user_id": user_id},
        ]
        result = get_user_id_from_messages(messages)
        assert result == user_id

    def test_no_user_id_returns_none(self):
        """Test returns None when no user_id found."""
        messages = [
            {"role": "user", "content": "Test"},
            HumanMessage(content="Test"),
        ]
        result = get_user_id_from_messages(messages)
        assert result is None

    def test_invalid_user_id_continues_search(self):
        """Test continues searching when user_id is invalid."""
        valid_id = uuid4()
        messages = [
            {"role": "user", "content": "Test", "user_id": "invalid-uuid"},
            {"role": "user", "content": "Test2", "user_id": str(valid_id)},
        ]
        result = get_user_id_from_messages(messages)
        assert result == valid_id

    def test_extract_from_last_message_first(self):
        """Test extracts from most recent message first."""
        id1 = uuid4()
        id2 = uuid4()
        messages = [
            {"role": "user", "content": "First", "user_id": str(id1)},
            {"role": "user", "content": "Last", "user_id": str(id2)},
        ]
        result = get_user_id_from_messages(messages)
        assert result == id2


@pytest.mark.unit
class TestCreateErrorCommand:
    """Test suite for create_error_command function."""

    def test_creates_valid_error_command(self):
        """Test creates valid Command with all expected properties."""
        error_msg = "Test error message"
        result = create_error_command(error_msg)

        # Validate Command structure
        assert isinstance(result, Command)
        assert hasattr(result, "update")
        assert hasattr(result, "goto")
        assert result.goto == "supervisor"

        # Validate messages
        messages = result.update["messages"]
        assert len(messages) >= 2  # Error message + handoff

        # Validate error message properties
        error_message = messages[0]
        assert error_msg in str(error_message)
        assert error_message.get("name") == "wealth_agent"

    def test_handles_different_error_messages(self):
        """Test handles different error messages correctly."""
        errors = [
            "No user_id found",
            "Knowledge base unavailable",
            "Invalid query",
        ]

        for error in errors:
            result = create_error_command(error)
            assert isinstance(result, Command)
            messages = result.update["messages"]
            assert error in str(messages[0])
