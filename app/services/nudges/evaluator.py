import asyncio
from typing import Any, AsyncIterator, Dict, List, Optional
from uuid import UUID

from app.core.config import config
from app.observability.logging_config import get_logger
from app.services.nudges.activity_counter import get_activity_counter
from app.services.nudges.strategies import get_strategy_registry
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
        self.strategy_registry = get_strategy_registry()

    async def evaluate_nudges_batch(self, user_ids: List[str], nudge_type: str, **context_kwargs) -> Dict[str, Any]:
        strategy = self.strategy_registry.get_strategy(nudge_type)
        if not strategy:
            logger.error(
                "evaluator.unknown_nudge_type",
                nudge_type=nudge_type,
                available_types=self.strategy_registry.list_available_strategies(),
            )
            return {"evaluated": 0, "queued": 0, "skipped": len(user_ids), "error": f"Unknown nudge type: {nudge_type}"}

        context = {
            "nudge_id": context_kwargs.get("nudge_id"),
            "notification_text": context_kwargs.get("notification_text"),
            "preview_text": context_kwargs.get("preview_text"),
            "metadata": context_kwargs,
        }

        evaluated = 0
        queued = 0
        skipped = 0
        results = []

        semaphore = asyncio.Semaphore(config.EVAL_CONCURRENCY_LIMIT)

        async def evaluate_user(user_id_str: str):
            async with semaphore:
                try:
                    user_id = UUID(user_id_str)
                    if not await self._check_common_conditions(user_id, nudge_type):
                        return {"user_id": user_id_str, "status": "skipped", "reason": "conditions_not_met"}
                    if not await strategy.validate_conditions(user_id):
                        return {"user_id": user_id_str, "status": "skipped", "reason": "strategy_conditions_not_met"}
                    candidate = await strategy.evaluate(user_id, context)
                    if not candidate:
                        return {"user_id": user_id_str, "status": "skipped", "reason": "no_candidate"}
                    message_id = await self._queue_nudge(candidate)
                    await strategy.cleanup(user_id)
                    return {
                        "user_id": user_id_str,
                        "status": "queued",
                        "nudge_type": nudge_type,
                        "priority": candidate.priority,
                        "message_id": message_id,
                    }
                except Exception as e:
                    logger.error(
                        "evaluator.user_evaluation_failed",
                        user_id=user_id_str,
                        nudge_type=nudge_type,
                        strategy=strategy.__class__.__name__,
                        error=str(e),
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
            "evaluator.batch_complete",
            nudge_type=nudge_type,
            strategy=strategy.__class__.__name__,
            evaluated=evaluated,
            queued=queued,
            skipped=skipped,
        )

        return {"evaluated": evaluated, "queued": queued, "skipped": skipped, "results": results}

    async def _check_common_conditions(self, user_id: UUID, nudge_type: str) -> bool:
        if not config.NUDGES_ENABLED:
            return False
        if not await self.activity_counter.check_rate_limits(user_id):
            logger.debug("evaluator.rate_limited", user_id=str(user_id))
            return False
        if await self.activity_counter.is_in_cooldown(user_id, nudge_type):
            logger.debug("evaluator.in_cooldown", user_id=str(user_id), nudge_type=nudge_type)
            return False
        if self._is_quiet_hours():
            logger.debug("evaluator.quiet_hours", user_id=str(user_id))
            return False
        return True

    async def _queue_nudge(self, candidate: NudgeCandidate) -> str:
        message = NudgeMessage(
            user_id=UUID(candidate.user_id),
            nudge_type=candidate.nudge_type,
            priority=candidate.priority,
            payload={
                "notification_text": candidate.notification_text,
                "preview_text": candidate.preview_text,
                "metadata": candidate.metadata,
            },
        )
        message_id = await self.sqs_manager.enqueue_nudge(message)
        await self.activity_counter.increment_nudge_count(UUID(candidate.user_id), candidate.nudge_type)
        return message_id

    def _is_quiet_hours(self) -> bool:
        from datetime import datetime

        current_hour = datetime.now().hour
        start = config.NUDGE_QUIET_HOURS_START
        end = config.NUDGE_QUIET_HOURS_END
        if start > end:
            return current_hour >= start or current_hour < end
        else:
            return start <= current_hour < end

    def register_custom_strategy(self, nudge_type: str, strategy_class):
        self.strategy_registry.register_strategy_class(nudge_type, strategy_class)
        logger.info(
            "evaluator.custom_strategy_registered", nudge_type=nudge_type, strategy_class=strategy_class.__name__
        )


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

    # TODO: Replace with actual FOS API call
    # This is mocked data for testing
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
