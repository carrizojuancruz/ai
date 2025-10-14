"""
Unit tests for app.services.nudges.models module.

Tests cover:
- NudgeMessage initialization and properties
- NudgeMessage to_dict serialization
- NudgeCandidate initialization and properties
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app.services.nudges.models import NudgeCandidate, NudgeMessage


class TestNudgeMessage:
    """Test NudgeMessage class."""

    def test_init_required_params(self):
        """Test initialization with required parameters."""
        user_id = uuid4()
        nudge_type = "test_nudge"
        priority = 5
        payload = {"key": "value"}

        message = NudgeMessage(
            user_id=user_id,
            nudge_type=nudge_type,
            priority=priority,
            payload=payload,
        )

        assert message.user_id == str(user_id)
        assert message.nudge_type == nudge_type
        assert message.priority == priority
        assert message.payload == payload
        assert message.channel == "app"  # default
        assert isinstance(message.message_id, str)
        assert isinstance(message.timestamp, datetime)
        assert isinstance(message.expires_at, datetime)
        assert message.deduplication_key == f"{user_id}:{nudge_type}"

    def test_init_all_params(self):
        """Test initialization with all parameters."""
        user_id = uuid4()
        nudge_type = "test_nudge"
        priority = 8
        payload = {"test": "data"}
        channel = "push"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

        message = NudgeMessage(
            user_id=user_id,
            nudge_type=nudge_type,
            priority=priority,
            payload=payload,
            channel=channel,
            expires_at=expires_at,
        )

        assert message.user_id == str(user_id)
        assert message.nudge_type == nudge_type
        assert message.priority == priority
        assert message.payload == payload
        assert message.channel == channel
        assert message.expires_at == expires_at
        assert message.deduplication_key == f"{user_id}:{nudge_type}"

    def test_init_default_expires_at(self):
        """Test that expires_at defaults to 12 hours from timestamp."""
        user_id = uuid4()
        nudge_type = "test_nudge"
        priority = 3
        payload = {"data": "test"}

        message = NudgeMessage(
            user_id=user_id,
            nudge_type=nudge_type,
            priority=priority,
            payload=payload,
        )

        expected_expires_at = message.timestamp + timedelta(hours=12)
        assert message.expires_at == expected_expires_at

    def test_init_unique_message_ids(self):
        """Test that each message gets a unique message_id."""
        user_id = uuid4()
        nudge_type = "test_nudge"
        priority = 5
        payload = {"key": "value"}

        message1 = NudgeMessage(
            user_id=user_id,
            nudge_type=nudge_type,
            priority=priority,
            payload=payload,
        )
        message2 = NudgeMessage(
            user_id=user_id,
            nudge_type=nudge_type,
            priority=priority,
            payload=payload,
        )

        assert message1.message_id != message2.message_id
        assert isinstance(UUID(message1.message_id), UUID)
        assert isinstance(UUID(message2.message_id), UUID)

    def test_to_dict_serialization(self):
        """Test to_dict method serializes correctly."""
        user_id = uuid4()
        nudge_type = "test_nudge"
        priority = 7
        payload = {"nested": {"data": "value"}}
        channel = "email"
        timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        expires_at = datetime(2024, 1, 1, 18, 0, 0, tzinfo=timezone.utc)

        message = NudgeMessage(
            user_id=user_id,
            nudge_type=nudge_type,
            priority=priority,
            payload=payload,
            channel=channel,
            expires_at=expires_at,
        )
        # Override timestamp for predictable test
        message.timestamp = timestamp

        result = message.to_dict()

        expected = {
            "messageId": message.message_id,
            "userId": str(user_id),
            "nudgeType": nudge_type,
            "priority": priority,
            "nudgePayload": payload,
            "channel": channel,
            "timestamp": timestamp.isoformat(),
            "expiresAt": expires_at.isoformat(),
            "deduplicationKey": f"{user_id}:{nudge_type}",
        }

        assert result == expected
        assert isinstance(result["timestamp"], str)
        assert isinstance(result["expiresAt"], str)

    def test_to_dict_with_default_expires_at(self):
        """Test to_dict with default expires_at."""
        user_id = uuid4()
        nudge_type = "test_nudge"
        priority = 4
        payload = {"simple": "payload"}

        message = NudgeMessage(
            user_id=user_id,
            nudge_type=nudge_type,
            priority=priority,
            payload=payload,
        )

        result = message.to_dict()

        assert result["expiresAt"] == message.expires_at.isoformat()
        assert result["channel"] == "app"


class TestNudgeCandidate:
    """Test NudgeCandidate class."""

    def test_init_required_params(self):
        """Test initialization with required parameters."""
        user_id = uuid4()
        nudge_type = "memory_nudge"
        priority = 6
        notification_text = "Don't forget your savings goal!"
        preview_text = "Savings reminder"

        candidate = NudgeCandidate(
            user_id=user_id,
            nudge_type=nudge_type,
            priority=priority,
            notification_text=notification_text,
            preview_text=preview_text,
        )

        assert candidate.user_id == user_id
        assert candidate.nudge_type == nudge_type
        assert candidate.priority == priority
        assert candidate.notification_text == notification_text
        assert candidate.preview_text == preview_text
        assert candidate.metadata == {}

    def test_init_with_metadata(self):
        """Test initialization with metadata."""
        user_id = uuid4()
        nudge_type = "goal_nudge"
        priority = 9
        notification_text = "Time to review your budget"
        preview_text = "Budget check-in"
        metadata = {"source": "memory", "memory_id": "mem_123", "confidence": 0.85}

        candidate = NudgeCandidate(
            user_id=user_id,
            nudge_type=nudge_type,
            priority=priority,
            notification_text=notification_text,
            preview_text=preview_text,
            metadata=metadata,
        )

        assert candidate.user_id == user_id
        assert candidate.nudge_type == nudge_type
        assert candidate.priority == priority
        assert candidate.notification_text == notification_text
        assert candidate.preview_text == preview_text
        assert candidate.metadata == metadata

    def test_init_empty_metadata_defaults_to_empty_dict(self):
        """Test that None metadata defaults to empty dict."""
        user_id = uuid4()
        nudge_type = "test_nudge"
        priority = 5
        notification_text = "Test notification"
        preview_text = "Test preview"

        candidate = NudgeCandidate(
            user_id=user_id,
            nudge_type=nudge_type,
            priority=priority,
            notification_text=notification_text,
            preview_text=preview_text,
            metadata=None,
        )

        assert candidate.metadata == {}

    def test_init_metadata_none_explicit(self):
        """Test explicit None metadata."""
        user_id = uuid4()
        nudge_type = "test_nudge"
        priority = 5
        notification_text = "Test notification"
        preview_text = "Test preview"

        candidate = NudgeCandidate(
            user_id=user_id,
            nudge_type=nudge_type,
            priority=priority,
            notification_text=notification_text,
            preview_text=preview_text,
        )

        assert candidate.metadata == {}

    def test_init_preserves_metadata_reference(self):
        """Test that metadata dict is stored as reference."""
        user_id = uuid4()
        nudge_type = "test_nudge"
        priority = 5
        notification_text = "Test notification"
        preview_text = "Test preview"
        metadata = {"mutable": True}

        candidate = NudgeCandidate(
            user_id=user_id,
            nudge_type=nudge_type,
            priority=priority,
            notification_text=notification_text,
            preview_text=preview_text,
            metadata=metadata,
        )

        # Modify original dict
        metadata["added"] = "value"

        # Should reflect in candidate (reference)
        assert candidate.metadata["added"] == "value"
