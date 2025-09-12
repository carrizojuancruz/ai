import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.queue import get_sqs_manager

logger = logging.getLogger(__name__)


class NudgeMessage:
    """Represents a nudge message from SQS."""

    def __init__(
        self,
        message_id: str,
        user_id: str,
        nudge_type: str,
        priority: int,
        nudge_payload: Dict[str, Any],
        channel: str,
        timestamp: str,
        expires_at: str,
        deduplication_key: str,
        receipt_handle: str,
    ):
        self.message_id = message_id
        self.user_id = user_id
        self.nudge_type = nudge_type
        self.priority = priority
        self.nudge_payload = nudge_payload
        self.channel = channel
        self.timestamp = timestamp
        self.expires_at = expires_at
        self.deduplication_key = deduplication_key
        self.receipt_handle = receipt_handle

    @classmethod
    def from_sqs_message(cls, message: Dict[str, Any]) -> "NudgeMessage":
        body = json.loads(message["Body"])
        return cls(
            message_id=body["messageId"],
            user_id=body["userId"],
            nudge_type=body["nudgeType"],
            priority=body["priority"],
            nudge_payload=body["nudgePayload"],
            channel=body["channel"],
            timestamp=body["timestamp"],
            expires_at=body["expiresAt"],
            deduplication_key=body["deduplicationKey"],
            receipt_handle=message["ReceiptHandle"],
        )

    def is_expired(self) -> bool:
        try:
            expires_dt = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) > expires_dt
        except Exception:
            return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "user_id": self.user_id,
            "nudge_type": self.nudge_type,
            "priority": self.priority,
            "channel": self.channel,
            "expired": self.is_expired(),
        }


class SqsConsumer:
    """Consumer for processing nudges from SQS queue."""

    def __init__(self):
        self.sqs_manager = get_sqs_manager()
        self.max_messages = 10

    async def poll_nudges(self, max_messages: Optional[int] = None) -> List[NudgeMessage]:
        try:
            logger.debug(f"nudge_consumer.polling: max_messages={max_messages or self.max_messages}")

            messages = await self.sqs_manager.receive_messages(max_messages=max_messages or self.max_messages)

            logger.debug(f"nudge_consumer.raw_messages: count={len(messages)}")

            nudges = []
            expired_count = 0
            parse_error_count = 0

            for message in messages:
                try:
                    nudge = NudgeMessage.from_sqs_message(message)
                    if not nudge.is_expired():
                        nudges.append(nudge)
                        logger.debug(
                            f"nudge_consumer.valid_nudge: message_id={nudge.message_id}, nudge_type={nudge.nudge_type}, user_id={nudge.user_id}"
                        )
                    else:
                        expired_count += 1
                        logger.debug(
                            f"nudge_consumer.expired_skipped: message_id={nudge.message_id}, expires_at={nudge.expires_at}"
                        )
                except Exception as e:
                    parse_error_count += 1
                    logger.error(f"nudge_consumer.parse_error: {str(e)}")
                    continue

            logger.info(
                f"nudge_consumer.polled: valid={len(nudges)}, expired={expired_count}, "
                f"parse_errors={parse_error_count}, total_raw={len(messages)}"
            )
            return nudges

        except Exception as e:
            logger.error(f"nudge_consumer.poll_failed: {str(e)}")
            return []

    async def delete_nudge(self, receipt_handle: str) -> bool:
        try:
            await self.sqs_manager.delete_message(receipt_handle)
            logger.info(f"nudge_consumer.deleted: receipt_handle={receipt_handle[:20]}...")
            return True
        except Exception as e:
            logger.error(f"nudge_consumer.delete_failed: receipt_handle={receipt_handle[:20]}..., error={str(e)}")
            return False

    async def delete_nudges(self, receipt_handles: List[str]) -> int:
        deleted_count = 0
        for receipt_handle in receipt_handles:
            if await self.delete_nudge(receipt_handle):
                deleted_count += 1
        return deleted_count


_sqs_consumer = None


def get_sqs_consumer() -> SqsConsumer:
    global _sqs_consumer
    if _sqs_consumer is None:
        _sqs_consumer = SqsConsumer()
    return _sqs_consumer
