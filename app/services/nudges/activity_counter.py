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
        now = datetime.now()
        count_key = f"{key}:{today}"
        previous_count = self._nudge_counts[count_key].get("count", 0)
        self._nudge_counts[count_key]["count"] = previous_count + 1
        self._last_nudge[key] = now
        logger.info(
            f"activity_counter.incremented: user_id={str(user_id)}, nudge_type={nudge_type}, date={today}, new_count={previous_count + 1}, timestamp={now.isoformat()}"
        )

    async def get_nudge_stats(self, user_id: UUID) -> NudgeStats:
        logger.debug(f"activity_counter.getting_stats: user_id={str(user_id)}")
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        nudges_today = 0
        nudges_week = 0
        last_nudge_time = None
        per_type_counts = {}
        for nudge_type in ["static_bill", "memory_icebreaker", "info_based"]:
            key = f"{user_id}:{nudge_type}"
            today_key = f"{key}:{today.isoformat()}"
            type_today_count = self._nudge_counts.get(today_key, {}).get("count", 0)
            nudges_today += type_today_count
            type_week_count = 0
            for i in range(7):
                day = (week_start + timedelta(days=i)).isoformat()
                day_key = f"{key}:{day}"
                type_week_count += self._nudge_counts.get(day_key, {}).get("count", 0)
            nudges_week += type_week_count
            if type_today_count > 0 or type_week_count > 0:
                per_type_counts[nudge_type] = {"today": type_today_count, "week": type_week_count}
            nudge_time = self._last_nudge.get(key)
            if nudge_time and (not last_nudge_time or nudge_time > last_nudge_time):
                last_nudge_time = nudge_time
        logger.debug(
            f"activity_counter.stats_calculated: user_id={str(user_id)}, nudges_today={nudges_today}, nudges_week={nudges_week}, per_type_counts={per_type_counts}, last_nudge={last_nudge_time.isoformat() if last_nudge_time else None}"
        )
        return NudgeStats(nudges_today=nudges_today, nudges_this_week=nudges_week, last_nudge=last_nudge_time)

    async def check_rate_limits(self, user_id: UUID) -> bool:
        stats = await self.get_nudge_stats(user_id)
        if stats.nudges_today >= config.NUDGE_MAX_PER_DAY:
            logger.warning(
                f"activity_counter.daily_rate_limit_exceeded: user_id={str(user_id)}, count={stats.nudges_today}, limit={config.NUDGE_MAX_PER_DAY}, last_nudge={stats.last_nudge.isoformat() if stats.last_nudge else None}"
            )
            return False
        if stats.nudges_this_week >= config.NUDGE_MAX_PER_WEEK:
            logger.warning(
                f"activity_counter.weekly_rate_limit_exceeded: user_id={str(user_id)}, count={stats.nudges_this_week}, limit={config.NUDGE_MAX_PER_WEEK}, last_nudge={stats.last_nudge.isoformat() if stats.last_nudge else None}"
            )
            return False
        logger.debug(
            f"activity_counter.within_rate_limits: user_id={str(user_id)}, daily_count={stats.nudges_today}, daily_limit={config.NUDGE_MAX_PER_DAY}, weekly_count={stats.nudges_this_week}, weekly_limit={config.NUDGE_MAX_PER_WEEK}"
        )
        return True

    async def set_cooldown(self, user_id: UUID, nudge_type: str, until: datetime) -> None:
        key = f"{user_id}:{nudge_type}"
        self._cooldowns[key] = until
        logger.info(
            f"activity_counter.cooldown_set: user_id={str(user_id)}, nudge_type={nudge_type}, until={until.isoformat()}"
        )

    async def is_in_cooldown(self, user_id: UUID, nudge_type: str) -> bool:
        key = f"{user_id}:{nudge_type}"
        cooldown_until = self._cooldowns.get(key)
        now = datetime.now()
        if cooldown_until and cooldown_until > now:
            remaining_seconds = (cooldown_until - now).total_seconds()
            logger.info(
                f"activity_counter.in_cooldown: user_id={str(user_id)}, nudge_type={nudge_type}, until={cooldown_until.isoformat()}, remaining_seconds={int(remaining_seconds)}"
            )
            return True
        if cooldown_until and cooldown_until <= now:
            del self._cooldowns[key]
            logger.debug(
                f"activity_counter.cooldown_expired: user_id={str(user_id)}, nudge_type={nudge_type}, expired_at={cooldown_until.isoformat()}"
            )
        return False

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
        expired_cooldowns = []
        now = datetime.now()
        for key, until in list(self._cooldowns.items()):
            if until <= now:
                expired_cooldowns.append(key)
                del self._cooldowns[key]
        logger.info(
            f"activity_counter.cleanup_complete: removed_counts={len(keys_to_delete)}, expired_cooldowns={len(expired_cooldowns)}, remaining_counts={len(self._nudge_counts)}, remaining_cooldowns={len(self._cooldowns)}"
        )


_activity_counter = None


def get_activity_counter() -> ActivityCounter:
    global _activity_counter
    if _activity_counter is None:
        _activity_counter = ActivityCounter()
    return _activity_counter
