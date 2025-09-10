from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Optional
from uuid import UUID

from app.core.config import config
from app.observability.logging_config import get_logger

logger = get_logger(__name__)


class NudgeStats:
    def __init__(self, nudges_today: int, nudges_this_week: int, last_nudge: Optional[datetime]):
        self.nudges_today = nudges_today
        self.nudges_this_week = nudges_this_week
        self.last_nudge = last_nudge


class ActivityCounter:
    def __init__(self):
        self._nudge_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._last_nudge: Dict[str, datetime] = {}
        self._cooldowns: Dict[str, datetime] = {}

    async def increment_nudge_count(self, user_id: UUID, nudge_type: str) -> None:
        key = f"{user_id}:{nudge_type}"
        today = datetime.now().date().isoformat()
        self._nudge_counts[f"{key}:{today}"]["count"] += 1
        self._last_nudge[key] = datetime.now()
        logger.info("activity_counter.incremented", user_id=str(user_id), nudge_type=nudge_type, date=today)

    async def get_nudge_stats(self, user_id: UUID) -> NudgeStats:
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        nudges_today = 0
        nudges_week = 0
        last_nudge_time = None
        for nudge_type in ["static_bill", "memory_icebreaker", "info_based"]:
            key = f"{user_id}:{nudge_type}"
            today_key = f"{key}:{today.isoformat()}"
            nudges_today += self._nudge_counts.get(today_key, {}).get("count", 0)
            for i in range(7):
                day = (week_start + timedelta(days=i)).isoformat()
                day_key = f"{key}:{day}"
                nudges_week += self._nudge_counts.get(day_key, {}).get("count", 0)
            nudge_time = self._last_nudge.get(key)
            if nudge_time and (not last_nudge_time or nudge_time > last_nudge_time):
                last_nudge_time = nudge_time
        return NudgeStats(nudges_today=nudges_today, nudges_this_week=nudges_week, last_nudge=last_nudge_time)

    async def check_rate_limits(self, user_id: UUID) -> bool:
        stats = await self.get_nudge_stats(user_id)
        if stats.nudges_today >= config.NUDGE_MAX_PER_DAY:
            logger.warning(
                "activity_counter.rate_limit_exceeded",
                user_id=str(user_id),
                limit_type="daily",
                count=stats.nudges_today,
                limit=config.NUDGE_MAX_PER_DAY,
            )
            return False
        if stats.nudges_this_week >= config.NUDGE_MAX_PER_WEEK:
            logger.warning(
                "activity_counter.rate_limit_exceeded",
                user_id=str(user_id),
                limit_type="weekly",
                count=stats.nudges_this_week,
                limit=config.NUDGE_MAX_PER_WEEK,
            )
            return False
        return True

    async def set_cooldown(self, user_id: UUID, nudge_type: str, until: datetime) -> None:
        key = f"{user_id}:{nudge_type}"
        self._cooldowns[key] = until
        logger.info(
            "activity_counter.cooldown_set", user_id=str(user_id), nudge_type=nudge_type, until=until.isoformat()
        )

    async def is_in_cooldown(self, user_id: UUID, nudge_type: str) -> bool:
        key = f"{user_id}:{nudge_type}"
        cooldown_until = self._cooldowns.get(key)
        if cooldown_until and cooldown_until > datetime.now():
            logger.debug(
                "activity_counter.in_cooldown",
                user_id=str(user_id),
                nudge_type=nudge_type,
                until=cooldown_until.isoformat(),
            )
            return True
        return False

    def cleanup_old_entries(self):
        cutoff = datetime.now() - timedelta(days=7)
        keys_to_delete = []
        for key in self._nudge_counts:
            if ":" in key:
                date_str = key.split(":")[-1]
                try:
                    entry_date = datetime.fromisoformat(date_str).date()
                    if entry_date < cutoff.date():
                        keys_to_delete.append(key)
                except Exception:
                    pass
        for key in keys_to_delete:
            del self._nudge_counts[key]
        logger.info("activity_counter.cleanup_complete", removed_entries=len(keys_to_delete))


_activity_counter = None


def get_activity_counter() -> ActivityCounter:
    global _activity_counter
    if _activity_counter is None:
        _activity_counter = ActivityCounter()
    return _activity_counter
