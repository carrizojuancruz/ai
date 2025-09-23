"""Unit tests for nudge models and validation."""

from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.nudge import NudgeChannel, NudgeRecord, NudgeStatus


class TestNudgeStatus:
    """Test NudgeStatus enum."""

    def test_nudge_status_values(self):
        """Test all nudge status enum values."""
        assert NudgeStatus.PENDING == "pending"
        assert NudgeStatus.PROCESSING == "processing"
        assert NudgeStatus.SENT == "sent"
        assert NudgeStatus.FAILED == "failed"
        assert NudgeStatus.CANCELLED == "cancelled"

    def test_nudge_status_from_string(self):
        """Test creating NudgeStatus from string values."""
        assert NudgeStatus("pending") == NudgeStatus.PENDING
        assert NudgeStatus("processing") == NudgeStatus.PROCESSING
        assert NudgeStatus("sent") == NudgeStatus.SENT
        assert NudgeStatus("failed") == NudgeStatus.FAILED
        assert NudgeStatus("cancelled") == NudgeStatus.CANCELLED

    def test_invalid_nudge_status(self):
        """Test invalid nudge status raises ValueError."""
        with pytest.raises(ValueError):
            NudgeStatus("invalid_status")


class TestNudgeChannel:
    """Test NudgeChannel enum."""

    def test_nudge_channel_values(self):
        """Test all nudge channel enum values."""
        assert NudgeChannel.EMAIL == "email"
        assert NudgeChannel.SMS == "sms"
        assert NudgeChannel.PUSH == "push"
        assert NudgeChannel.IN_APP == "in_app"

    def test_nudge_channel_from_string(self):
        """Test creating NudgeChannel from string values."""
        assert NudgeChannel("email") == NudgeChannel.EMAIL
        assert NudgeChannel("sms") == NudgeChannel.SMS
        assert NudgeChannel("push") == NudgeChannel.PUSH
        assert NudgeChannel("in_app") == NudgeChannel.IN_APP

    def test_invalid_nudge_channel(self):
        """Test invalid nudge channel raises ValueError."""
        with pytest.raises(ValueError):
            NudgeChannel("invalid_channel")


class TestNudgeRecord:
    """Test NudgeRecord Pydantic model."""

    def test_valid_nudge_record(self):
        """Test creating valid nudge record."""
        nudge_id = uuid4()
        user_id = uuid4()
        created_at = datetime.utcnow()

        record = NudgeRecord(
            id=nudge_id,
            user_id=user_id,
            nudge_type="market_update",
            priority=5,
            status=NudgeStatus.PENDING,
            channel=NudgeChannel.EMAIL,
            notification_text="Market update available",
            preview_text="Check out the latest market trends",
            created_at=created_at
        )

        assert record.id == nudge_id
        assert record.user_id == user_id
        assert record.nudge_type == "market_update"
        assert record.priority == 5
        assert record.status == NudgeStatus.PENDING
        assert record.channel == NudgeChannel.EMAIL
        assert record.notification_text == "Market update available"
        assert record.preview_text == "Check out the latest market trends"
        assert record.created_at == created_at
        assert record.updated_at is None
        assert record.scheduled_for is None
        assert record.sent_at is None
        assert record.error_message is None
        assert record.metadata == {}

    def test_nudge_record_with_metadata(self):
        """Test nudge record with metadata."""
        metadata = {"source": "portfolio_tracker", "urgency": "high"}

        record = NudgeRecord(
            id=uuid4(),
            user_id=uuid4(),
            nudge_type="portfolio_alert",
            priority=1,
            status=NudgeStatus.PROCESSING,
            channel=NudgeChannel.PUSH,
            notification_text="Portfolio alert",
            preview_text="Your portfolio needs attention",
            created_at=datetime.utcnow(),
            metadata=metadata
        )

        assert record.metadata == metadata

    def test_nudge_record_priority_validation(self):
        """Test nudge record priority validation."""
        # Valid priorities
        for priority in [1, 5, 10]:
            record = NudgeRecord(
                id=uuid4(),
                user_id=uuid4(),
                nudge_type="test",
                priority=priority,
                status=NudgeStatus.PENDING,
                channel=NudgeChannel.EMAIL,
                notification_text="Test",
                preview_text="Test",
                created_at=datetime.utcnow()
            )
            assert record.priority == priority

        # Invalid priorities
        for invalid_priority in [0, 11, -1]:
            with pytest.raises(ValidationError):
                NudgeRecord(
                    id=uuid4(),
                    user_id=uuid4(),
                    nudge_type="test",
                    priority=invalid_priority,
                    status=NudgeStatus.PENDING,
                    channel=NudgeChannel.EMAIL,
                    notification_text="Test",
                    preview_text="Test",
                    created_at=datetime.utcnow()
                )

    def test_nudge_record_required_fields(self):
        """Test nudge record required field validation."""
        base_data = {
            "id": uuid4(),
            "user_id": uuid4(),
            "nudge_type": "test",
            "priority": 5,
            "status": NudgeStatus.PENDING,
            "channel": NudgeChannel.EMAIL,
            "notification_text": "Test",
            "preview_text": "Test",
            "created_at": datetime.utcnow()
        }

        # Valid record
        record = NudgeRecord(**base_data)
        assert record.id == base_data["id"]

        # Test missing required fields
        required_fields = ["id", "user_id", "nudge_type", "priority", "status", "channel", "notification_text", "preview_text", "created_at"]

        for field in required_fields:
            test_data = base_data.copy()
            del test_data[field]

            with pytest.raises(ValidationError):
                NudgeRecord(**test_data)

    def test_nudge_record_string_conversion(self):
        """Test nudge record string representation."""
        record = NudgeRecord(
            id=uuid4(),
            user_id=uuid4(),
            nudge_type="test_nudge",
            priority=5,
            status=NudgeStatus.PENDING,
            channel=NudgeChannel.EMAIL,
            notification_text="Test notification",
            preview_text="Test preview",
            created_at=datetime.utcnow()
        )

        str_repr = str(record)
        assert "test_nudge" in str_repr
        assert "pending" in str_repr
        assert "email" in str_repr

    def test_nudge_record_dict_conversion(self):
        """Test nudge record dictionary conversion."""
        nudge_id = uuid4()
        user_id = uuid4()
        created_at = datetime.utcnow()

        record = NudgeRecord(
            id=nudge_id,
            user_id=user_id,
            nudge_type="test",
            priority=5,
            status=NudgeStatus.PENDING,
            channel=NudgeChannel.EMAIL,
            notification_text="Test",
            preview_text="Test",
            created_at=created_at
        )

        record_dict = record.model_dump()

        assert record_dict["id"] == nudge_id
        assert record_dict["user_id"] == user_id
        assert record_dict["nudge_type"] == "test"
        assert record_dict["priority"] == 5
        assert record_dict["status"] == "pending"
        assert record_dict["channel"] == "email"
        assert record_dict["notification_text"] == "Test"
        assert record_dict["preview_text"] == "Test"
        assert record_dict["created_at"] == created_at
