"""Unit tests for finance agent helpers."""

from uuid import UUID

from app.agents.supervisor.finance_agent.helpers import (
    create_error_command,
    extract_text_from_content,
    get_last_user_message_text,
    get_user_id_from_messages,
    rows_to_json,
    serialize_sample_row,
)


class TestExtractTextFromContent:
    """Test extract_text_from_content function."""

    def test_extract_string_content(self):
        """Test extracting text from string content."""
        content = "Hello world"
        result = extract_text_from_content(content)
        assert result == "Hello world"

    def test_extract_list_content(self):
        """Test extracting text from list content."""
        content = [
            {"text": "Hello"},
            {"content": " world"},
            {"other": "ignored"}
        ]
        result = extract_text_from_content(content)
        assert result == "Hello\n world"

    def test_extract_empty_content(self):
        """Test extracting text from empty content."""
        result = extract_text_from_content(None)
        assert result == ""

    def test_extract_non_string_content(self):
        """Test extracting text from non-string content."""
        result = extract_text_from_content(123)
        assert result == "123"


class TestGetLastUserMessageText:
    """Test get_last_user_message_text function."""

    def test_get_last_human_message(self):
        """Test getting text from last HumanMessage."""
        from langchain_core.messages import HumanMessage

        messages = [
            HumanMessage(content="First message"),
            HumanMessage(content="Last message")
        ]
        result = get_last_user_message_text(messages)
        assert result == "Last message"

    def test_get_last_user_dict_message(self):
        """Test getting text from last user dict message."""
        messages = [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "Assistant response"},
            {"role": "user", "content": "Last message"}
        ]
        result = get_last_user_message_text(messages)
        assert result == "Last message"

    def test_no_user_messages(self):
        """Test when there are no user messages."""
        messages = [
            {"role": "assistant", "content": "Assistant response"}
        ]
        result = get_last_user_message_text(messages)
        assert result == ""


class TestGetUserIdFromMessages:
    """Test get_user_id_from_messages function."""

    def test_get_user_id_from_dict(self):
        """Test getting user_id from dict message."""
        user_id = UUID("12345678-1234-5678-9012-123456789012")
        messages = [
            {"role": "user", "user_id": str(user_id)}
        ]
        result = get_user_id_from_messages(messages)
        assert result == user_id

    def test_get_user_id_uuid_object(self):
        """Test getting user_id when it's already a UUID object."""
        user_id = UUID("12345678-1234-5678-9012-123456789012")
        messages = [
            {"role": "user", "user_id": user_id}
        ]
        result = get_user_id_from_messages(messages)
        assert result == user_id

    def test_invalid_or_missing_user_id(self):
        """Test handling invalid or missing user_id."""
        # Invalid UUID
        messages_invalid = [
            {"role": "user", "user_id": "invalid-uuid"}
        ]
        result_invalid = get_user_id_from_messages(messages_invalid)
        assert result_invalid is None

        # No user_id present
        messages_no_id = [
            {"role": "user", "content": "Hello"}
        ]
        result_no_id = get_user_id_from_messages(messages_no_id)
        assert result_no_id is None


class TestSerializeSampleRow:
    """Test serialize_sample_row function."""

    def test_serialize_dict_row(self):
        """Test serializing a dict row."""
        from datetime import date

        row = {
            "id": UUID("12345678-1234-5678-9012-123456789012"),
            "amount": 100.5,
            "date": date(2023, 1, 1),
            "name": "Test"
        }
        result = serialize_sample_row(row)
        expected = {
            "id": "12345678-1234-5678-9012-123456789012",
            "amount": 100.5,
            "date": "2023-01-01",
            "name": "Test"
        }
        assert result == expected

    def test_serialize_non_dict_row(self):
        """Test serializing non-dict row."""
        row = "string"
        result = serialize_sample_row(row)
        assert result == "string"


class TestRowsToJson:
    """Test rows_to_json function."""

    def test_rows_to_json_conversion(self):
        """Test converting rows to JSON string."""
        rows = [
            {"id": 1, "name": "Test"},
            {"id": 2, "name": "Test2"}
        ]
        result = rows_to_json(rows)
        expected = '[{"id":1,"name":"Test"},{"id":2,"name":"Test2"}]'
        assert result == expected


class TestCreateErrorCommand:
    """Test create_error_command function."""

    def test_create_error_command_structure(self):
        """Test that error command has correct structure."""
        error_message = "Test error"
        command = create_error_command(error_message)

        assert command.update["messages"][0]["content"] == error_message
        assert command.update["messages"][0]["name"] == "finance_agent"
        assert command.goto == "supervisor"
