import asyncio
import random
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional
from uuid import UUID

from app.core.config import config
from app.observability.logging_config import get_logger
from app.repositories.s3_vectors_store import get_s3_vectors_store
from app.services.nudges.activity_counter import get_activity_counter
from app.services.nudges.bill_detector import get_bill_detector
from app.services.nudges.selector import NudgeSelector
from app.services.nudges.templates import NudgeRegistry
from app.services.queue import NudgeMessage, get_sqs_manager

logger = get_logger(__name__)


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


class NudgeEvaluator:
    def __init__(self):
        self.sqs_manager = get_sqs_manager()
        self.activity_counter = get_activity_counter()
        self.bill_detector = get_bill_detector()
        self.selector = NudgeSelector()
        self.registry = NudgeRegistry()
        self.s3_vectors = get_s3_vectors_store()

    async def evaluate_nudges_batch(
        self,
        user_ids: List[str],
        nudge_type: str,
        nudge_id: Optional[str] = None,
        notification_text: Optional[str] = None,
        preview_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        evaluated = 0
        queued = 0
        skipped = 0
        results = []

        semaphore = asyncio.Semaphore(config.EVAL_CONCURRENCY_LIMIT)

        async def evaluate_user(user_id_str: str):
            async with semaphore:
                try:
                    user_id = UUID(user_id_str)
                    result = await self._evaluate_single_user(
                        user_id, nudge_type, nudge_id, notification_text, preview_text
                    )
                    return result
                except Exception as e:
                    logger.error(
                        "evaluator.user_evaluation_failed", user_id=user_id_str, nudge_type=nudge_type, error=str(e)
                    )
                    return {"user_id": user_id_str, "status": "error", "reason": str(e)}

        tasks = [evaluate_user(uid) for uid in user_ids]
        user_results = await asyncio.gather(*tasks)

        for result in user_results:
            evaluated += 1
            if result["status"] == "queued":
                queued += 1
            else:
                skipped += 1
            results.append(result)

        logger.info(
            "evaluator.batch_complete", nudge_type=nudge_type, evaluated=evaluated, queued=queued, skipped=skipped
        )

        return {"evaluated": evaluated, "queued": queued, "skipped": skipped, "results": results}

    async def _evaluate_single_user(
        self,
        user_id: UUID,
        nudge_type: str,
        nudge_id: Optional[str] = None,
        notification_text: Optional[str] = None,
        preview_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not config.NUDGES_ENABLED:
            return {"user_id": str(user_id), "status": "skipped", "reason": "nudges_disabled"}

        if not await self.activity_counter.check_rate_limits(user_id):
            return {"user_id": str(user_id), "status": "skipped", "reason": "rate_limited"}

        if await self.activity_counter.is_in_cooldown(user_id, nudge_type):
            return {"user_id": str(user_id), "status": "skipped", "reason": "in_cooldown"}

        if self._is_quiet_hours():
            return {"user_id": str(user_id), "status": "skipped", "reason": "quiet_hours"}

        candidate = None

        if nudge_type == "static_bill":
            candidate = await self._evaluate_bill_nudge(user_id)
        elif nudge_type == "memory_icebreaker":
            candidate = await self._evaluate_memory_nudge(user_id)
        elif nudge_type == "info_based":
            candidate = await self._evaluate_info_nudge(user_id, nudge_id, notification_text, preview_text)
        else:
            return {"user_id": str(user_id), "status": "skipped", "reason": "unknown_nudge_type"}

        if not candidate:
            return {"user_id": str(user_id), "status": "skipped", "reason": "no_candidate"}

        try:
            message = NudgeMessage(
                user_id=user_id,
                nudge_type=nudge_type,
                priority=candidate.priority,
                payload={
                    "notification_text": candidate.notification_text,
                    "preview_text": candidate.preview_text,
                    "metadata": candidate.metadata,
                },
            )

            message_id = await self.sqs_manager.enqueue_nudge(message)

            await self.activity_counter.increment_nudge_count(user_id, nudge_type)

            return {
                "user_id": str(user_id),
                "status": "queued",
                "nudge_type": nudge_type,
                "priority": candidate.priority,
                "message_id": message_id,
            }

        except Exception as e:
            logger.error("evaluator.queue_failed", user_id=str(user_id), nudge_type=nudge_type, error=str(e))
            return {"user_id": str(user_id), "status": "error", "reason": f"queue_failed: {str(e)}"}

    async def _evaluate_bill_nudge(self, user_id: UUID) -> Optional[NudgeCandidate]:
        try:
            bills = await self.bill_detector.detect_upcoming_bills(user_id)

            if not bills:
                return None

            most_urgent = bills[0]

            priority = self.bill_detector.assign_bill_priority(most_urgent)

            texts = await self.bill_detector.get_bill_notification_text(most_urgent)

            return NudgeCandidate(
                user_id=user_id,
                nudge_type="static_bill",
                priority=priority,
                notification_text=texts["notification_text"],
                preview_text=texts["preview_text"],
                metadata={"bill": most_urgent.to_dict()},
            )

        except Exception as e:
            logger.error("evaluator.bill_evaluation_failed", user_id=str(user_id), error=str(e))
            return None

    async def _evaluate_memory_nudge(self, user_id: UUID) -> Optional[NudgeCandidate]:
        try:
            memories = await self.s3_vectors.search_by_filter(
                filter_dict={"user_id": str(user_id), "importance_bin": "high"}, limit=10
            )

            if not memories:
                return None

            selected_memory = random.choice(memories)

            memory_text = selected_memory.get("text", "")[:100]
            notification_text = f"Remember this? {memory_text}..."
            preview_text = "Memory from your past"

            priority = 2 if selected_memory.get("importance_bin") == "high" else 1

            return NudgeCandidate(
                user_id=user_id,
                nudge_type="memory_icebreaker",
                priority=priority,
                notification_text=notification_text,
                preview_text=preview_text,
                metadata={"memory_id": selected_memory.get("id"), "memory_text": memory_text},
            )

        except Exception as e:
            logger.error("evaluator.memory_evaluation_failed", user_id=str(user_id), error=str(e))
            return None

    async def _evaluate_info_nudge(
        self, user_id: UUID, nudge_id: str, notification_text: str, preview_text: str
    ) -> Optional[NudgeCandidate]:
        try:
            evaluators = {
                "spending_alert": self._check_spending_increase,
                "goal_milestone": self._check_goal_progress,
                "budget_warning": self._check_budget_usage,
                "subscription_reminder": self._check_upcoming_subscription,
                "savings_opportunity": self._check_savings_potential,
            }

            evaluator = evaluators.get(nudge_id)
            if not evaluator:
                logger.warning("evaluator.unknown_nudge_id", nudge_id=nudge_id, user_id=str(user_id))
                return None

            should_send = await evaluator(user_id)

            if not should_send:
                return None

            priority = self._get_info_nudge_priority(nudge_id)

            return NudgeCandidate(
                user_id=user_id,
                nudge_type="info_based",
                priority=priority,
                notification_text=notification_text,
                preview_text=preview_text,
                metadata={"nudge_id": nudge_id, "evaluated_at": datetime.now(timezone.utc).isoformat()},
            )

        except Exception as e:
            logger.error("evaluator.info_evaluation_failed", user_id=str(user_id), nudge_id=nudge_id, error=str(e))
            return None

    async def _check_spending_increase(self, user_id: UUID) -> bool:
        return random.random() > 0.7

    async def _check_goal_progress(self, user_id: UUID) -> bool:
        return random.random() > 0.8

    async def _check_budget_usage(self, user_id: UUID) -> bool:
        return random.random() > 0.75

    async def _check_upcoming_subscription(self, user_id: UUID) -> bool:
        return random.random() > 0.85

    async def _check_savings_potential(self, user_id: UUID) -> bool:
        return random.random() > 0.9

    def _get_info_nudge_priority(self, nudge_id: str) -> int:
        priority_map = {
            "payment_failed": 5,
            "spending_alert": 4,
            "goal_milestone": 3,
            "budget_warning": 3,
            "subscription_reminder": 2,
            "savings_opportunity": 1,
        }
        return priority_map.get(nudge_id, 2)

    def _is_quiet_hours(self) -> bool:
        current_hour = datetime.now().hour
        start = config.NUDGE_QUIET_HOURS_START
        end = config.NUDGE_QUIET_HOURS_END

        if start > end:
            return current_hour >= start or current_hour < end
        else:
            return start <= current_hour < end


_nudge_evaluator = None


def get_nudge_evaluator() -> NudgeEvaluator:
    global _nudge_evaluator
    if _nudge_evaluator is None:
        _nudge_evaluator = NudgeEvaluator()
    return _nudge_evaluator


async def iter_active_users(
    *, page_size: int = None, max_pages: int = None, timeout_ms: int = None
) -> AsyncIterator[List[str]]:
    page_size = page_size or config.FOS_USERS_PAGE_SIZE
    max_pages = max_pages or config.FOS_USERS_MAX_PAGES

    mock_users = [
        "ba5c5db4-d3fb-4ca8-9445-1c221ea502a8",
        "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "98765432-1234-5678-90ab-cdef12345678",
    ]

    for i in range(0, len(mock_users), page_size):
        if max_pages and i // page_size >= max_pages:
            break

        page = mock_users[i : i + page_size]
        if page:
            yield page

        await asyncio.sleep(0.1)
