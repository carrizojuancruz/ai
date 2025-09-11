
from typing import Any, Dict, Optional
from uuid import UUID


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
