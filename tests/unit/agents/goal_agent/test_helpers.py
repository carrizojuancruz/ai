"""Tests for the Goal Agent Helpers."""

from langchain_core.messages import HumanMessage

from app.agents.supervisor.goal_agent.helpers import (
    create_error_command,
    get_last_user_message_text,
    get_user_id_from_messages,
)


class TestCreateErrorCommand:
    """Test cases for create_error_command function."""

    def test_create_error_command_structure(self):
        """Test that create_error_command returns proper Command structure."""
        # Arrange
        error_message = "Test error message"

        # Act
        result = create_error_command(error_message)

        # Assert
        assert result is not None
        assert hasattr(result, 'update')
        assert hasattr(result, 'goto')

        # Check update structure
        update_data = result.update
        assert "messages" in update_data
        assert len(update_data["messages"]) == 2

        # Check first message (error message)
        error_msg = update_data["messages"][0]
        assert error_msg["role"] == "assistant"
        assert error_msg["content"] == error_message
        assert error_msg["name"] == "goal_agent"

        # Check second message (handoff)
        handoff_msg = update_data["messages"][1]
        assert "goal_agent" in str(handoff_msg)
        assert "supervisor" in str(handoff_msg)

        # Check goto
        assert result.goto == "supervisor"


class TestGetLastUserMessageText:
    """Test cases for get_last_user_message_text function."""

    def test_get_last_human_message(self):
        """Test extracting text from last HumanMessage and handling no user messages."""
        # Arrange - Test with multiple HumanMessage objects
        messages = [
            HumanMessage(content="First message"),
            HumanMessage(content="Second message"),
            HumanMessage(content="Last message")
        ]

        # Act
        result = get_last_user_message_text(messages)

        # Assert
        assert result == "Last message"

        # Verify no user messages case
        messages_no_user = [
            {"role": "assistant", "content": "Assistant message"},
            {"role": "system", "content": "System message"}
        ]
        result_no_user = get_last_user_message_text(messages_no_user)
        assert result_no_user == ""


class TestGetUserIdFromMessages:
    """Test cases for get_user_id_from_messages function."""

    def test_get_user_id_from_messages(self):
        """Test that get_user_id_from_messages returns None (placeholder implementation)."""
        # Arrange
        messages = [
            HumanMessage(content="Test message")
        ]

        # Act
        result = get_user_id_from_messages(messages)

        # Assert
        assert result is None
