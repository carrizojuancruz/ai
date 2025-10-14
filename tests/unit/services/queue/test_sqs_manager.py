import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.services.queue.sqs_manager import NudgeMessage, SQSManager, get_sqs_manager


class TestNudgeMessage:
    def test_initialization_with_required_fields(self):
        user_id = uuid4()
        payload = {"key": "value"}

        message = NudgeMessage(
            user_id=user_id,
            nudge_type="test_nudge",
            priority=5,
            payload=payload
        )

        assert message.user_id == str(user_id)
        assert message.nudge_type == "test_nudge"
        assert message.priority == 5
        assert message.payload == payload
        assert message.channel == "push"
        assert isinstance(message.message_id, str)
        assert message.deduplication_key == f"{user_id}:test_nudge"
        assert isinstance(message.timestamp, datetime)
        assert isinstance(message.expires_at, datetime)

    def test_initialization_with_custom_channel_and_expiry(self):
        user_id = uuid4()
        custom_expiry = datetime.now(timezone.utc) + timedelta(hours=24)

        message = NudgeMessage(
            user_id=user_id,
            nudge_type="urgent",
            priority=10,
            payload={"data": "test"},
            channel="email",
            expires_at=custom_expiry
        )

        assert message.channel == "email"
        assert message.expires_at == custom_expiry

    def test_default_expiry_is_12_hours(self):
        message = NudgeMessage(
            user_id=uuid4(),
            nudge_type="test",
            priority=1,
            payload={}
        )

        expected_expiry = message.timestamp + timedelta(hours=12)
        assert abs((message.expires_at - expected_expiry).total_seconds()) < 1

    def test_to_dict_complete_data(self):
        user_id = uuid4()
        payload = {"amount": 100, "description": "test"}
        custom_expiry = datetime.now(timezone.utc) + timedelta(hours=6)

        message = NudgeMessage(
            user_id=user_id,
            nudge_type="payment_reminder",
            priority=3,
            payload=payload,
            channel="sms",
            expires_at=custom_expiry
        )

        result = message.to_dict()

        assert result["messageId"] == message.message_id
        assert result["userId"] == str(user_id)
        assert result["nudgeType"] == "payment_reminder"
        assert result["priority"] == 3
        assert result["nudgePayload"] == payload
        assert result["channel"] == "sms"
        assert result["timestamp"] == message.timestamp.isoformat()
        assert result["expiresAt"] == custom_expiry.isoformat()
        assert result["deduplicationKey"] == f"{user_id}:payment_reminder"


class TestSQSManager:
    @pytest.fixture
    def mock_config(self):
        with patch("app.services.queue.sqs_manager.config") as mock:
            mock.is_sqs_enabled.return_value = True
            mock.SQS_QUEUE_REGION = "us-east-1"
            mock.SQS_NUDGES_AI_ICEBREAKER = "https://sqs.us-east-1.amazonaws.com/123456789/test-queue"
            mock.SQS_MAX_MESSAGES = 10
            mock.SQS_VISIBILITY_TIMEOUT = 30
            mock.SQS_WAIT_TIME_SECONDS = 20
            yield mock

    @pytest.fixture
    def mock_boto3(self):
        with patch("app.services.queue.sqs_manager.boto3") as mock:
            mock_client = MagicMock()
            mock.client.return_value = mock_client
            yield mock, mock_client

    def test_initialization_success(self, mock_config, mock_boto3):
        _, mock_client = mock_boto3

        manager = SQSManager()

        assert manager.queue_url == "https://sqs.us-east-1.amazonaws.com/123456789/test-queue"
        assert manager.sqs_client == mock_client
        assert manager._in_flight_messages == {}

    def test_initialization_fails_when_sqs_disabled(self, mock_config):
        mock_config.is_sqs_enabled.return_value = False

        with pytest.raises(ValueError, match="SQS_NUDGES_AI_ICEBREAKER is not configured"):
            SQSManager()

    @pytest.mark.asyncio
    async def test_enqueue_nudge_success(self, mock_config, mock_boto3):
        _, mock_client = mock_boto3
        mock_client.send_message.return_value = {"MessageId": "msg-123"}

        manager = SQSManager()
        nudge = NudgeMessage(
            user_id=uuid4(),
            nudge_type="test",
            priority=5,
            payload={"key": "value"}
        )

        message_id = await manager.enqueue_nudge(nudge)

        assert message_id == "msg-123"
        assert nudge.deduplication_key in manager._in_flight_messages
        mock_client.send_message.assert_called_once()
        call_kwargs = mock_client.send_message.call_args.kwargs
        assert call_kwargs["QueueUrl"] == manager.queue_url
        assert "MessageBody" in call_kwargs
        assert "MessageAttributes" in call_kwargs

    @pytest.mark.asyncio
    async def test_enqueue_nudge_with_message_attributes(self, mock_config, mock_boto3):
        _, mock_client = mock_boto3
        mock_client.send_message.return_value = {"MessageId": "msg-456"}

        manager = SQSManager()
        user_id = uuid4()
        nudge = NudgeMessage(
            user_id=user_id,
            nudge_type="payment",
            priority=10,
            payload={"amount": 500}
        )

        await manager.enqueue_nudge(nudge)

        call_kwargs = mock_client.send_message.call_args.kwargs
        attrs = call_kwargs["MessageAttributes"]
        assert attrs["Priority"]["StringValue"] == "10"
        assert attrs["DeduplicationKey"]["StringValue"] == f"{user_id}:payment"
        assert attrs["UserId"]["StringValue"] == str(user_id)
        assert attrs["NudgeType"]["StringValue"] == "payment"
        assert "Timestamp" in attrs

    @pytest.mark.asyncio
    async def test_enqueue_nudge_handles_exception(self, mock_config, mock_boto3):
        _, mock_client = mock_boto3
        mock_client.send_message.side_effect = Exception("SQS Error")

        manager = SQSManager()
        nudge = NudgeMessage(
            user_id=uuid4(),
            nudge_type="test",
            priority=1,
            payload={}
        )

        with pytest.raises(Exception, match="SQS Error"):
            await manager.enqueue_nudge(nudge)

    @pytest.mark.asyncio
    async def test_receive_messages_success(self, mock_config, mock_boto3):
        _, mock_client = mock_boto3
        mock_client.receive_message.return_value = {
            "Messages": [
                {
                    "MessageId": "msg-1",
                    "ReceiptHandle": "handle-1",
                    "Body": json.dumps({"data": "test1"}),
                    "MessageAttributes": {
                        "Priority": {"StringValue": "5"},
                        "NudgeType": {"StringValue": "type1"},
                        "UserId": {"StringValue": "user-1"},
                        "Timestamp": {"StringValue": "2025-01-01T00:00:00+00:00"}
                    }
                },
                {
                    "MessageId": "msg-2",
                    "ReceiptHandle": "handle-2",
                    "Body": json.dumps({"data": "test2"}),
                    "MessageAttributes": {
                        "Priority": {"StringValue": "10"},
                        "NudgeType": {"StringValue": "type2"},
                        "UserId": {"StringValue": "user-2"},
                        "Timestamp": {"StringValue": "2025-01-01T00:00:00+00:00"}
                    }
                }
            ]
        }

        manager = SQSManager()
        messages = await manager.receive_messages()

        assert len(messages) == 2
        assert messages[0]["MessageId"] == "msg-2"
        assert messages[1]["MessageId"] == "msg-1"

    @pytest.mark.asyncio
    async def test_receive_messages_empty(self, mock_config, mock_boto3):
        _, mock_client = mock_boto3
        mock_client.receive_message.return_value = {}

        manager = SQSManager()
        messages = await manager.receive_messages()

        assert messages == []

    @pytest.mark.asyncio
    async def test_receive_messages_with_max_messages_param(self, mock_config, mock_boto3):
        _, mock_client = mock_boto3
        mock_client.receive_message.return_value = {"Messages": []}

        manager = SQSManager()
        await manager.receive_messages(max_messages=5)

        call_kwargs = mock_client.receive_message.call_args.kwargs
        assert call_kwargs["MaxNumberOfMessages"] == 5

    @pytest.mark.asyncio
    async def test_receive_messages_uses_default_max(self, mock_config, mock_boto3):
        _, mock_client = mock_boto3
        mock_client.receive_message.return_value = {"Messages": []}

        manager = SQSManager()
        await manager.receive_messages()

        call_kwargs = mock_client.receive_message.call_args.kwargs
        assert call_kwargs["MaxNumberOfMessages"] == 10

    @pytest.mark.asyncio
    async def test_receive_messages_sorts_by_priority_descending(self, mock_config, mock_boto3):
        _, mock_client = mock_boto3
        mock_client.receive_message.return_value = {
            "Messages": [
                {
                    "MessageId": "msg-low",
                    "MessageAttributes": {
                        "Priority": {"StringValue": "1"},
                        "Timestamp": {"StringValue": "2025-01-01T00:00:00+00:00"}
                    }
                },
                {
                    "MessageId": "msg-high",
                    "MessageAttributes": {
                        "Priority": {"StringValue": "10"},
                        "Timestamp": {"StringValue": "2025-01-01T00:00:00+00:00"}
                    }
                },
                {
                    "MessageId": "msg-mid",
                    "MessageAttributes": {
                        "Priority": {"StringValue": "5"},
                        "Timestamp": {"StringValue": "2025-01-01T00:00:00+00:00"}
                    }
                }
            ]
        }

        manager = SQSManager()
        messages = await manager.receive_messages()

        assert messages[0]["MessageId"] == "msg-high"
        assert messages[1]["MessageId"] == "msg-mid"
        assert messages[2]["MessageId"] == "msg-low"

    @pytest.mark.asyncio
    async def test_receive_messages_sorts_by_timestamp_when_priority_equal(self, mock_config, mock_boto3):
        _, mock_client = mock_boto3
        mock_client.receive_message.return_value = {
            "Messages": [
                {
                    "MessageId": "msg-later",
                    "MessageAttributes": {
                        "Priority": {"StringValue": "5"},
                        "Timestamp": {"StringValue": "2025-01-02T00:00:00+00:00"}
                    }
                },
                {
                    "MessageId": "msg-earlier",
                    "MessageAttributes": {
                        "Priority": {"StringValue": "5"},
                        "Timestamp": {"StringValue": "2025-01-01T00:00:00+00:00"}
                    }
                }
            ]
        }

        manager = SQSManager()
        messages = await manager.receive_messages()

        assert messages[0]["MessageId"] == "msg-earlier"
        assert messages[1]["MessageId"] == "msg-later"

    @pytest.mark.asyncio
    async def test_receive_messages_handles_exception(self, mock_config, mock_boto3):
        _, mock_client = mock_boto3
        mock_client.receive_message.side_effect = Exception("Network error")

        manager = SQSManager()

        with pytest.raises(Exception, match="Network error"):
            await manager.receive_messages()

    @pytest.mark.asyncio
    async def test_delete_message_success(self, mock_config, mock_boto3):
        _, mock_client = mock_boto3

        manager = SQSManager()
        receipt_handle = "test-receipt-handle-12345"

        await manager.delete_message(receipt_handle)

        mock_client.delete_message.assert_called_once_with(
            QueueUrl=manager.queue_url,
            ReceiptHandle=receipt_handle
        )

    @pytest.mark.asyncio
    async def test_delete_message_handles_exception(self, mock_config, mock_boto3):
        _, mock_client = mock_boto3
        mock_client.delete_message.side_effect = Exception("Delete failed")

        manager = SQSManager()

        with pytest.raises(Exception, match="Delete failed"):
            await manager.delete_message("test-handle")

    @pytest.mark.asyncio
    async def test_get_queue_depth_success(self, mock_config, mock_boto3):
        _, mock_client = mock_boto3
        mock_client.get_queue_attributes.return_value = {
            "Attributes": {"ApproximateNumberOfMessages": "42"}
        }

        manager = SQSManager()
        depth = await manager.get_queue_depth()

        assert depth == 42
        mock_client.get_queue_attributes.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_queue_depth_returns_zero_on_exception(self, mock_config, mock_boto3):
        _, mock_client = mock_boto3
        mock_client.get_queue_attributes.side_effect = Exception("API error")

        manager = SQSManager()
        depth = await manager.get_queue_depth()

        assert depth == 0

    @pytest.mark.asyncio
    async def test_get_queue_depth_handles_missing_attribute(self, mock_config, mock_boto3):
        _, mock_client = mock_boto3
        mock_client.get_queue_attributes.return_value = {"Attributes": {}}

        manager = SQSManager()
        depth = await manager.get_queue_depth()

        assert depth == 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("message_time,latest_time,expected", [
        ("2025-01-02T00:00:00+00:00", "2025-01-01T00:00:00+00:00", True),
        ("2025-01-01T00:00:00+00:00", "2025-01-01T00:00:00+00:00", True),
        ("2025-01-01T00:00:00+00:00", "2025-01-02T00:00:00+00:00", False),
    ])
    async def test_is_latest_nudge_timestamp_comparison(self, mock_config, mock_boto3, message_time, latest_time, expected):
        manager = SQSManager()
        user_id = "test-user"
        nudge_type = "test-nudge"
        dedup_key = f"{user_id}:{nudge_type}"

        manager._in_flight_messages[dedup_key] = datetime.fromisoformat(latest_time)

        result = await manager.is_latest_nudge(user_id, nudge_type, message_time)

        assert result == expected

    @pytest.mark.asyncio
    async def test_is_latest_nudge_returns_true_when_no_in_flight(self, mock_config, mock_boto3):
        manager = SQSManager()

        result = await manager.is_latest_nudge("user-1", "nudge-1", "2025-01-01T00:00:00+00:00")

        assert result is True

    @pytest.mark.asyncio
    async def test_is_latest_nudge_handles_invalid_timestamp(self, mock_config, mock_boto3):
        manager = SQSManager()
        user_id = "test-user"
        nudge_type = "test-nudge"
        dedup_key = f"{user_id}:{nudge_type}"

        manager._in_flight_messages[dedup_key] = datetime.now(timezone.utc)

        result = await manager.is_latest_nudge(user_id, nudge_type, "invalid-timestamp")

        assert result is True


class TestGetSQSManager:
    @patch("app.services.queue.sqs_manager.boto3")
    @patch("app.services.queue.sqs_manager.config")
    def test_singleton_pattern(self, mock_config, mock_boto3):
        mock_config.is_sqs_enabled.return_value = True
        mock_config.SQS_QUEUE_REGION = "us-east-1"
        mock_config.SQS_NUDGES_AI_ICEBREAKER = "https://sqs.us-east-1.amazonaws.com/123456789/test-queue"
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        with patch("app.services.queue.sqs_manager._sqs_manager", None):
            manager1 = get_sqs_manager()
            manager2 = get_sqs_manager()

            assert manager1 is manager2

    @patch("app.services.queue.sqs_manager.boto3")
    @patch("app.services.queue.sqs_manager.config")
    def test_creates_new_instance_when_none(self, mock_config, mock_boto3):
        mock_config.is_sqs_enabled.return_value = True
        mock_config.SQS_QUEUE_REGION = "us-east-1"
        mock_config.SQS_NUDGES_AI_ICEBREAKER = "https://sqs.us-east-1.amazonaws.com/123456789/test-queue"
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        with patch("app.services.queue.sqs_manager._sqs_manager", None):
            manager = get_sqs_manager()

            assert isinstance(manager, SQSManager)
