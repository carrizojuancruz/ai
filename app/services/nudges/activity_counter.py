from collections import defaultdict
from datetime import datetime
from typing import Dict
from uuid import UUID

from app.observability.logging_config import get_logger

logger = get_logger(__name__)


class ActivityCounter:
    def __init__(self):
        self._nudge_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._last_nudge: Dict[str, datetime] = {}

    async def increment_nudge_count(self, user_id: UUID, nudge_type: str) -> None:
        key = f"{user_id}:{nudge_type}"
        today = datetime.now().date().isoformat()
        now = datetime.now()
        count_key = f"{key}:{today}"
        previous_count = self._nudge_counts[count_key].get("count", 0)
        self._nudge_counts[count_key]["count"] = previous_count + 1
        self._last_nudge[key] = now
        logger.info(
            f"activity_counter.incremented: user_id={str(user_id)}, nudge_type={nudge_type}, date={today}, new_count={previous_count + 1}, timestamp={now.isoformat()}"
        )


_activity_counter = None


def get_activity_counter() -> ActivityCounter:
    global _activity_counter
    if _activity_counter is None:
        _activity_counter = ActivityCounter()
    return _activity_counter
