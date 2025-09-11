from collections import defaultdict
from datetime import datetime, timedelta
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


    def cleanup_old_entries(self):
        logger.debug("activity_counter.cleanup_started")
        cutoff = datetime.now() - timedelta(days=7)
        keys_to_delete = []
        for key in self._nudge_counts:
            if ":" in key:
                date_str = key.split(":")[-1]
                try:
                    entry_date = datetime.fromisoformat(date_str).date()
                    if entry_date < cutoff.date():
                        keys_to_delete.append(key)
                except Exception as e:
                    logger.debug(
                        f"activity_counter.cleanup_parse_error: key={key}, error={str(e)}"
                    )
        for key in keys_to_delete:
            del self._nudge_counts[key]
        logger.info(
            f"activity_counter.cleanup_complete: removed_counts={len(keys_to_delete)}, remaining_counts={len(self._nudge_counts)}"
        )


_activity_counter = None


def get_activity_counter() -> ActivityCounter:
    global _activity_counter
    if _activity_counter is None:
        _activity_counter = ActivityCounter()
    return _activity_counter
