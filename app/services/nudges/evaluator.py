import asyncio
from typing import Any, AsyncIterator, Dict, List
from uuid import UUID

from app.core.config import config
from app.observability.logging_config import get_logger
from app.services.nudges.activity_counter import get_activity_counter
from app.services.nudges.models import NudgeCandidate
from app.services.nudges.strategies import get_strategy_registry
from app.services.queue import NudgeMessage, get_sqs_manager

logger = get_logger(__name__)


class NudgeEvaluator:
    def __init__(self):
        self.sqs_manager = get_sqs_manager()
        self.activity_counter = get_activity_counter()
        self.strategy_registry = get_strategy_registry()

    async def evaluate_nudges_batch(self, user_ids: List[str], nudge_type: str, **context_kwargs) -> Dict[str, Any]:
        logger.info(
            f"evaluator.batch_started: nudge_type={nudge_type}, user_count={len(user_ids)}, context_keys={list(context_kwargs.keys())}"
        )

        strategy = self.strategy_registry.get_strategy(nudge_type)
        if not strategy:
            logger.error(
                f"evaluator.unknown_nudge_type: nudge_type={nudge_type}, available_types={self.strategy_registry.list_available_strategies()}"
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
                    logger.debug(f"evaluator.evaluating_user: user_id={user_id_str}, nudge_type={nudge_type}")

                    if not await strategy.validate_conditions(user_id):
                        logger.debug(
                            f"evaluator.strategy_conditions_failed: user_id={user_id_str}, strategy={strategy.__class__.__name__}"
                        )
                        return {"user_id": user_id_str, "status": "skipped", "reason": "strategy_conditions_not_met"}

                    candidate = await strategy.evaluate(user_id, context)
                    if not candidate:
                        logger.debug(f"evaluator.no_candidate_found: user_id={user_id_str}, nudge_type={nudge_type}")
                        return {"user_id": user_id_str, "status": "skipped", "reason": "no_candidate"}

                    logger.info(
                        f"evaluator.candidate_found: user_id={user_id_str}, nudge_type={candidate.nudge_type}, priority={candidate.priority}, has_metadata={bool(candidate.metadata)}"
                    )

                    message_id = await self._queue_nudge(candidate)
                    if hasattr(strategy, "cleanup"):
                        await strategy.cleanup(user_id)

                    logger.info(
                        f"evaluator.nudge_queued: user_id={user_id_str}, nudge_type={nudge_type}, priority={candidate.priority}, message_id={message_id}"
                    )

                    return {
                        "user_id": user_id_str,
                        "status": "queued",
                        "nudge_type": nudge_type,
                        "priority": candidate.priority,
                        "message_id": message_id,
                    }
                except Exception as e:
                    logger.error(
                        f"evaluator.user_evaluation_failed: user_id={user_id_str}, nudge_type={nudge_type}, strategy={strategy.__class__.__name__}, error={str(e)}"
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
            f"evaluator.batch_complete: nudge_type={nudge_type}, strategy={strategy.__class__.__name__}, evaluated={evaluated}, queued={queued}, skipped={skipped}"
        )

        return {"evaluated": evaluated, "queued": queued, "skipped": skipped, "results": results}

    async def _queue_nudge(self, candidate: NudgeCandidate) -> str:
        channel = "app" if candidate.nudge_type == "memory_icebreaker" else "push"

        message = NudgeMessage(
            user_id=candidate.user_id,
            nudge_type=candidate.nudge_type,
            priority=candidate.priority,
            payload={
                "notification_text": candidate.notification_text,
                "preview_text": candidate.preview_text,
                "metadata": candidate.metadata,
            },
            channel=channel,
        )

        logger.debug(
            f"evaluator.queueing_nudge: user_id={str(candidate.user_id)}, nudge_type={candidate.nudge_type}, priority={candidate.priority}, text_preview={candidate.preview_text[:50] if candidate.preview_text else None}"
        )

        message_id = await self.sqs_manager.enqueue_nudge(message)
        await self.activity_counter.increment_nudge_count(candidate.user_id, candidate.nudge_type)

        logger.debug(f"evaluator.nudge_queued_successfully: user_id={str(candidate.user_id)}, message_id={message_id}")

        return message_id

    def register_custom_strategy(self, nudge_type: str, strategy_class):
        self.strategy_registry.register_strategy_class(nudge_type, strategy_class)
        logger.info(
            f"evaluator.custom_strategy_registered: nudge_type={nudge_type}, strategy_class={strategy_class.__name__}"
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
        "5fbcf7ba-bf83-47e0-b8f5-b46cf9cec0f6",
        "98765432-1234-5678-90ab-cdef12345678",
    ]

    for i in range(0, len(mock_users), page_size):
        if max_pages and i // page_size >= max_pages:
            break

        page = mock_users[i : i + page_size]
        if page:
            yield page

        await asyncio.sleep(0.1)
