import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import boto3
from botocore.config import Config as BotoConfig

from app.core.config import config
from app.observability.logging_config import get_logger

logger = get_logger(__name__)


class NudgeMessage:
    def __init__(
        self,
        user_id: UUID,
        nudge_type: str,
        priority: int,
        payload: Dict[str, Any],
        channel: str = "push",
        expires_at: Optional[datetime] = None,
    ):
        self.message_id = str(uuid4())
        self.user_id = str(user_id)
        self.nudge_type = nudge_type
        self.priority = priority
        self.payload = payload
        self.channel = channel
        self.timestamp = datetime.now(timezone.utc)
        self.expires_at = expires_at or (self.timestamp + timedelta(hours=12))
        self.deduplication_key = f"{user_id}:{nudge_type}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "messageId": self.message_id,
            "userId": self.user_id,
            "nudgeType": self.nudge_type,
            "priority": self.priority,
            "nudgePayload": self.payload,
            "channel": self.channel,
            "timestamp": self.timestamp.isoformat(),
            "expiresAt": self.expires_at.isoformat(),
            "deduplicationKey": self.deduplication_key,
        }


class SQSManager:
    def __init__(self):
        boto_config = BotoConfig(region_name=config.SQS_QUEUE_REGION, retries={"max_attempts": 3, "mode": "adaptive"})
        self.sqs_client = boto3.client("sqs", config=boto_config)
        self.queue_url = config.SQS_QUEUE_URL
        self._in_flight_messages: Dict[str, datetime] = {}

    async def enqueue_nudge(self, nudge: NudgeMessage) -> str:
        try:
            dedup_key = nudge.deduplication_key

            logger.debug(
                f"sqs.enqueue_attempt: user_id={nudge.user_id}, nudge_type={nudge.nudge_type}, "
                f"priority={nudge.priority}, dedup_key={dedup_key}, expires_at={nudge.expires_at.isoformat()}"
            )

            await self._mark_as_replaced(dedup_key)
            message_attributes = {
                "Priority": {"DataType": "Number", "StringValue": str(nudge.priority)},
                "DeduplicationKey": {"DataType": "String", "StringValue": dedup_key},
                "Timestamp": {"DataType": "String", "StringValue": nudge.timestamp.isoformat()},
                "UserId": {"DataType": "String", "StringValue": nudge.user_id},
                "NudgeType": {"DataType": "String", "StringValue": nudge.nudge_type},
            }
            response = self.sqs_client.send_message(
                QueueUrl=self.queue_url, MessageBody=json.dumps(nudge.to_dict()), MessageAttributes=message_attributes
            )
            message_id = response["MessageId"]
            self._in_flight_messages[dedup_key] = nudge.timestamp
            logger.info(
                f"sqs.nudge_enqueued: message_id={message_id}, user_id={nudge.user_id}, "
                f"nudge_type={nudge.nudge_type}, priority={nudge.priority}, dedup_key={dedup_key}"
            )
            return message_id
        except Exception as e:
            logger.error(
                f"sqs.enqueue_failed: {str(e)}", extra={"user_id": nudge.user_id, "nudge_type": nudge.nudge_type}
            )
            raise

    async def _mark_as_replaced(self, dedup_key: str) -> None:
        if dedup_key in self._in_flight_messages:
            logger.info(
                f"sqs.message_replaced: dedup_key={dedup_key}, "
                f"previous_timestamp={self._in_flight_messages[dedup_key].isoformat()}"
            )

    async def receive_messages(self, max_messages: Optional[int] = None) -> List[Dict[str, Any]]:
        max_messages = max_messages or config.SQS_MAX_MESSAGES

        logger.debug(
            f"sqs.receive_attempt: max_messages={max_messages}, queue_url={self.queue_url}, "
            f"visibility_timeout={config.SQS_VISIBILITY_TIMEOUT}, wait_time={config.SQS_WAIT_TIME_SECONDS}"
        )

        try:
            response = self.sqs_client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=max_messages or config.SQS_MAX_MESSAGES,
                MessageAttributeNames=["All"],
                VisibilityTimeout=config.SQS_VISIBILITY_TIMEOUT,
                WaitTimeSeconds=config.SQS_WAIT_TIME_SECONDS,
            )
            messages = response.get("Messages", [])

            if not messages:
                logger.debug("sqs.no_messages_available")
                return []

            logger.debug(f"sqs.raw_messages_received: count={len(messages)}")

            for i, message in enumerate(messages):
                message_id = message.get("MessageId", "unknown")
                attributes = message.get("MessageAttributes", {})
                nudge_type = attributes.get("NudgeType", {}).get("StringValue", "unknown")
                user_id = attributes.get("UserId", {}).get("StringValue", "unknown")
                priority = attributes.get("Priority", {}).get("StringValue", "1")
                logger.debug(
                    f"sqs.message_{i}: id={message_id}, type={nudge_type}, user={user_id}, priority={priority}"
                )

            sorted_messages = sorted(
                messages,
                key=lambda m: (
                    -int(m.get("MessageAttributes", {}).get("Priority", {}).get("StringValue", "1")),
                    m.get("MessageAttributes", {}).get("Timestamp", {}).get("StringValue", ""),
                ),
            )
            if sorted_messages:
                priorities = [
                    m.get("MessageAttributes", {}).get("Priority", {}).get("StringValue", "1") for m in sorted_messages
                ]
                nudge_types = [
                    m.get("MessageAttributes", {}).get("NudgeType", {}).get("StringValue", "unknown")
                    for m in sorted_messages
                ]

                max_priority = sorted_messages[0].get("MessageAttributes", {}).get("Priority", {}).get("StringValue")
                logger.info(
                    f"sqs.messages_received: count={len(sorted_messages)}, priorities={priorities}, "
                    f"nudge_types={nudge_types}, max_priority={max_priority}"
                )
            return sorted_messages
        except Exception as e:
            logger.error(
                f"sqs.receive_failed: {str(e)} (type: {type(e).__name__}), queue_url={self.queue_url}", exc_info=True
            )
            raise

    async def delete_message(self, receipt_handle: str) -> None:
        try:
            logger.debug(f"sqs.delete_attempt: receipt_handle={receipt_handle[:20]}...")

            self.sqs_client.delete_message(QueueUrl=self.queue_url, ReceiptHandle=receipt_handle)

            logger.info(f"sqs.message_deleted: receipt_handle={receipt_handle[:20]}...")
        except Exception as e:
            logger.error(
                f"sqs.delete_failed: receipt_handle={receipt_handle[:20]}..., error={str(e)} (type: {type(e).__name__})"
            )
            raise

    async def get_queue_depth(self) -> int:
        try:
            response = self.sqs_client.get_queue_attributes(
                QueueUrl=self.queue_url, AttributeNames=["ApproximateNumberOfMessages"]
            )
            depth = int(response["Attributes"].get("ApproximateNumberOfMessages", 0))
            logger.debug(f"sqs.queue_depth: {depth}")
            return depth
        except Exception as e:
            logger.error(f"sqs.get_depth_failed: {str(e)}")
            return 0

    async def is_latest_nudge(self, user_id: str, nudge_type: str, timestamp: str) -> bool:
        dedup_key = f"{user_id}:{nudge_type}"
        latest_timestamp = self._in_flight_messages.get(dedup_key)
        if not latest_timestamp:
            return True
        try:
            message_time = datetime.fromisoformat(timestamp)
            if message_time >= latest_timestamp:
                return True
            else:
                logger.info(
                    f"sqs.stale_message_detected: user_id={user_id}, nudge_type={nudge_type}, "
                    f"message_timestamp={timestamp}, latest_timestamp={latest_timestamp.isoformat()}"
                )
                return False
        except Exception as e:
            logger.error(f"sqs.timestamp_comparison_failed: {str(e)}")
            return True


_sqs_manager = None


def get_sqs_manager() -> SQSManager:
    global _sqs_manager
    if _sqs_manager is None:
        _sqs_manager = SQSManager()
    return _sqs_manager
