
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4


class NudgeMessage:
    """Message model for nudge data."""

    def __init__(
        self,
        user_id: UUID,
        nudge_type: str,
        priority: int,
        payload: Dict[str, Any],
        channel: str = "app",
        expires_at: Optional[datetime] = None,
        deduplication_key: Optional[str] = None,
    ):
        self.message_id = str(uuid4())
        self.user_id = str(user_id)
        self.nudge_type = nudge_type
        self.priority = priority
        self.payload = payload
        self.channel = channel
        self.timestamp = datetime.now(timezone.utc)
        self.expires_at = expires_at or (self.timestamp + timedelta(hours=12))
        self.deduplication_key = deduplication_key or f"{user_id}:{nudge_type}"

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


class NudgeCandidate:
    def __init__(
        self,
        user_id: UUID,
        nudge_type: str,
        priority: int,
        notification_text: str,
        preview_text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.user_id = user_id
        self.nudge_type = nudge_type
        self.priority = priority
        self.notification_text = notification_text
        self.preview_text = preview_text
        self.metadata = metadata or {}
