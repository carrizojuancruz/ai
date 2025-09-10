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
                "sqs.nudge_enqueued",
                message_id=message_id,
                user_id=nudge.user_id,
                nudge_type=nudge.nudge_type,
                priority=nudge.priority,
                deduplication_key=dedup_key,
            )
            return message_id
        except Exception as e:
            logger.error("sqs.enqueue_failed", user_id=nudge.user_id, nudge_type=nudge.nudge_type, error=str(e))
            raise

    async def _mark_as_replaced(self, dedup_key: str) -> None:
        if dedup_key in self._in_flight_messages:
            logger.info(
                "sqs.message_replaced",
                deduplication_key=dedup_key,
                previous_timestamp=self._in_flight_messages[dedup_key].isoformat(),
            )

    async def receive_messages(self, max_messages: Optional[int] = None) -> List[Dict[str, Any]]:
        try:
            response = self.sqs_client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=max_messages or config.SQS_MAX_MESSAGES,
                MessageAttributeNames=["All"],
                VisibilityTimeout=config.SQS_VISIBILITY_TIMEOUT,
                WaitTimeSeconds=config.SQS_WAIT_TIME_SECONDS,
            )
            messages = response.get("Messages", [])
            sorted_messages = sorted(
                messages,
                key=lambda m: (
                    -int(m.get("MessageAttributes", {}).get("Priority", {}).get("StringValue", "1")),
                    m.get("MessageAttributes", {}).get("Timestamp", {}).get("StringValue", ""),
                ),
            )
            logger.info(
                "sqs.messages_received",
                count=len(sorted_messages),
                max_priority=sorted_messages[0].get("MessageAttributes", {}).get("Priority", {}).get("StringValue")
                if sorted_messages
                else None,
            )
            return sorted_messages
        except Exception as e:
            logger.error("sqs.receive_failed", error=str(e))
            raise

    async def delete_message(self, receipt_handle: str) -> None:
        try:
            self.sqs_client.delete_message(QueueUrl=self.queue_url, ReceiptHandle=receipt_handle)
            logger.debug("sqs.message_deleted", receipt_handle=receipt_handle[:20] + "...")
        except Exception as e:
            logger.error("sqs.delete_failed", receipt_handle=receipt_handle[:20] + "...", error=str(e))
            raise

    async def get_queue_depth(self) -> int:
        try:
            response = self.sqs_client.get_queue_attributes(
                QueueUrl=self.queue_url, AttributeNames=["ApproximateNumberOfMessages"]
            )
            depth = int(response["Attributes"].get("ApproximateNumberOfMessages", 0))
            logger.debug("sqs.queue_depth", depth=depth)
            return depth
        except Exception as e:
            logger.error("sqs.get_depth_failed", error=str(e))
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
                    "sqs.stale_message_detected",
                    user_id=user_id,
                    nudge_type=nudge_type,
                    message_timestamp=timestamp,
                    latest_timestamp=latest_timestamp.isoformat(),
                )
                return False
        except Exception as e:
            logger.error("sqs.timestamp_comparison_failed", error=str(e))
            return True

_sqs_manager = None

def get_sqs_manager() -> SQSManager:
    global _sqs_manager
    if _sqs_manager is None:
        _sqs_manager = SQSManager()
    return _sqs_manager
