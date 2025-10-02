from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class NudgeStatus(str, Enum):
    """Nudge status enumeration."""

    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NudgeChannel(str, Enum):
    """Nudge delivery channel enumeration."""

    APP = "app"
    PUSH = "push"

class NudgeRecord(BaseModel):
    """Pydantic model for nudge records."""

    id: UUID
    user_id: UUID
    nudge_type: str = Field(..., max_length=50)
    priority: int = Field(..., ge=1, le=10)
    status: NudgeStatus
    channel: NudgeChannel
    notification_text: str
    preview_text: str
    created_at: datetime
    topic: str | None = None
    memory_id: str | None = Field(None, max_length=255)
    importance: str | None = None
    memory_text: str | None = None

    class Config:
        from_attributes = True
