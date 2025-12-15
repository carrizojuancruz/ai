import asyncio
import logging
from typing import Any, AsyncIterator, Dict, List, Optional
from uuid import UUID

import httpx

from app.core.app_state import get_fos_nudge_manager
from app.core.config import config
from app.models.nudge import NudgeChannel
from app.observability.logging_config import get_logger
from app.services.nudges.activity_counter import get_activity_counter
from app.services.nudges.models import NudgeCandidate, NudgeMessage
from app.services.nudges.strategies import get_strategy_registry
from app.services.queue import get_sqs_manager

logger = get_logger(__name__)


class NudgeEvaluator:
    def __init__(self):
        self.sqs_manager = get_sqs_manager()
        self.fos_manager = get_fos_nudge_manager()
        self.activity_counter = get_activity_counter()
        self.strategy_registry = get_strategy_registry()

    async def evaluate_nudges_batch(self, user_ids: List[str], nudge_type: str, **context_kwargs) -> Dict[str, Any]:
        logger.info(
            f"evaluator.batch_started: nudge_type={nudge_type}, user_count={len(user_ids)}, context_keys={list(context_kwargs.keys())}"
        )

        strategy = self.strategy_registry.get_strategy(nudge_type)
        if not strategy:
            return self._handle_unknown_strategy(nudge_type, len(user_ids))

        context = self._build_context(context_kwargs)

        candidates_results = await self._generate_candidates(user_ids, strategy, context, nudge_type)

        existing_memory_ids = await self._get_existing_memory_ids(candidates_results)

        final_results = await self._process_and_queue_candidates(
            candidates_results, existing_memory_ids, strategy, nudge_type
        )

        return self._aggregate_results(final_results, nudge_type, strategy)

    def _handle_unknown_strategy(self, nudge_type: str, user_count: int) -> Dict[str, Any]:
        logger.error(
            f"evaluator.unknown_nudge_type: nudge_type={nudge_type}, available_types={self.strategy_registry.list_available_strategies()}"
        )
        return {"evaluated": 0, "queued": 0, "skipped": user_count, "error": f"Unknown nudge type: {nudge_type}"}

    def _build_context(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "nudge_id": kwargs.get("nudge_id"),
            "notification_text": kwargs.get("notification_text"),
            "preview_text": kwargs.get("preview_text"),
            "metadata": kwargs,
        }

    async def _generate_candidates(
        self, user_ids: List[str], strategy: Any, context: Dict[str, Any], nudge_type: str
    ) -> List[tuple[Dict[str, Any], Optional[NudgeCandidate]]]:
        semaphore = asyncio.Semaphore(config.EVAL_CONCURRENCY_LIMIT)

        async def evaluate_single_user(user_id_str: str):
            async with semaphore:
                try:
                    user_id = UUID(user_id_str)
                    logger.debug(f"evaluator.evaluating_user: user_id={user_id_str}, nudge_type={nudge_type}")

                    if not await strategy.validate_conditions(user_id):
                        return {
                            "user_id": user_id_str,
                            "status": "skipped",
                            "reason": "strategy_conditions_not_met",
                        }, None

                    candidate = await strategy.evaluate(user_id, context)
                    if not candidate:
                        return {"user_id": user_id_str, "status": "skipped", "reason": "no_candidate"}, None

                    logger.info(
                        f"evaluator.candidate_found: user_id={user_id_str}, nudge_type={candidate.nudge_type}, priority={candidate.priority}"
                    )
                    return {"user_id": user_id_str, "status": "pending_check"}, candidate

                except Exception as e:
                    logger.error(
                        f"evaluator.user_evaluation_failed: user_id={user_id_str}, nudge_type={nudge_type}, error={str(e)}"
                    )
                    return {"user_id": user_id_str, "status": "error", "reason": str(e)}, None

        tasks = [evaluate_single_user(uid) for uid in user_ids]
        return await asyncio.gather(*tasks)

    async def _get_existing_memory_ids(
        self, candidates_results: List[tuple[Dict[str, Any], Optional[NudgeCandidate]]]
    ) -> set[str]:
        memory_ids = []
        for _, candidate in candidates_results:
            if candidate and candidate.nudge_type == "memory_icebreaker":
                mem_id = candidate.metadata.get("memory_id")
                if mem_id:
                    memory_ids.append(mem_id)

        if not memory_ids:
            return set()

        try:
            existing = await self.fos_manager.check_batch_memory_nudges_existence(memory_ids)
            logger.info(f"evaluator.batch_check_complete: checked={len(memory_ids)}, existing={len(existing)}")
            return set(existing)
        except Exception as e:
            logger.error(f"evaluator.batch_check_failed: error={str(e)}")
            return set()

    async def _process_and_queue_candidates(
        self,
        candidates_results: List[tuple[Dict[str, Any], Optional[NudgeCandidate]]],
        existing_memory_ids: set[str],
        strategy: Any,
        nudge_type: str,
    ) -> List[Dict[str, Any]]:
        final_results = []

        for result, candidate in candidates_results:
            if not candidate:
                final_results.append(result)
                continue

            if candidate.nudge_type == "memory_icebreaker":
                mem_id = candidate.metadata.get("memory_id")
                if mem_id and mem_id in existing_memory_ids:
                    logger.info(f"evaluator.duplicate_nudge_found: user_id={candidate.user_id}, memory_id={mem_id}")
                    final_results.append(
                        {"user_id": str(candidate.user_id), "status": "skipped", "reason": "duplicate_nudge"}
                    )
                    continue

            try:
                message_id = await self._queue_nudge(candidate)
                if hasattr(strategy, "cleanup"):
                    await strategy.cleanup(candidate.user_id)

                logger.info(
                    f"evaluator.nudge_queued: user_id={str(candidate.user_id)}, nudge_type={nudge_type}, message_id={message_id}"
                )

                final_results.append(
                    {
                        "user_id": str(candidate.user_id),
                        "status": "queued",
                        "nudge_type": nudge_type,
                        "priority": candidate.priority,
                        "message_id": message_id,
                    }
                )
            except Exception as e:
                logger.error(f"evaluator.queue_failed: user_id={candidate.user_id}, error={str(e)}")
                final_results.append(
                    {"user_id": str(candidate.user_id), "status": "error", "reason": f"Queue failed: {str(e)}"}
                )

        return final_results

    def _aggregate_results(
        self, results: List[Dict[str, Any]], nudge_type: str, strategy: Any
    ) -> Dict[str, Any]:
        evaluated = len(results)
        queued = sum(1 for r in results if r["status"] == "queued")
        skipped = sum(1 for r in results if r["status"] != "queued")

        logger.info(
            f"evaluator.batch_complete: nudge_type={nudge_type}, strategy={strategy.__class__.__name__}, "
            f"evaluated={evaluated}, queued={queued}, skipped={skipped}"
        )

        return {"evaluated": evaluated, "queued": queued, "skipped": skipped, "results": results}

    async def _queue_nudge(self, candidate: NudgeCandidate) -> str:
        if candidate.nudge_type == "memory_icebreaker":
            target_memory_id = candidate.metadata.get("memory_id") if candidate.metadata else None
            
            if target_memory_id:
                exists = await self.fos_manager.check_memory_nudge_exists(candidate.user_id, target_memory_id)
                if exists:
                    logger.info(f"evaluator.duplicate_nudge_found: user_id={candidate.user_id}, memory_id={target_memory_id}")
                    return "duplicate"

        channel = NudgeChannel.APP if candidate.nudge_type == "memory_icebreaker" else NudgeChannel.PUSH

        deduplication_key = None
        if candidate.nudge_type == "memory_icebreaker" and "memory_id" in candidate.metadata:
            deduplication_key = f"{candidate.user_id}:{candidate.nudge_type}:{candidate.metadata['memory_id']}"

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
            deduplication_key=deduplication_key,
        )

        logger.debug(
            f"evaluator.queueing_nudge: user_id={str(candidate.user_id)}, nudge_type={candidate.nudge_type}, priority={candidate.priority}, text_preview={candidate.preview_text[:50] if candidate.preview_text else None}"
        )

        if message.nudge_type == "memory_icebreaker":
            message_id = await self.fos_manager.enqueue_nudge(message)
        else:
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
    page_size = page_size or getattr(config, "FOS_USERS_PAGE_SIZE", 100)
    max_pages = max_pages or getattr(config, "FOS_USERS_MAX_PAGES", 10)

    if not config.FOS_SERVICE_URL:
        raise ValueError("FOS_SERVICE_URL not configured")

    base_url = config.FOS_SERVICE_URL.rstrip("/")
    url = f"{base_url}/internal/users/list"

    skip = 0
    pages_yielded = 0

    headers = {}
    if config.FOS_API_KEY:
        headers["Authorization"] = f"Bearer {config.FOS_API_KEY}"
    elif config.FOS_SECRETS_ID:
        logger.warning("FOS_SECRETS_ID configured but secret fetching not implemented")

    async with httpx.AsyncClient(timeout=timeout_ms or 30.0) as client:
        while True:
            if max_pages and pages_yielded >= max_pages:
                break

            params = {"skip": skip, "limit": page_size, "is_active": True}

            logger.debug(f"Fetching users page: skip={skip}, limit={page_size}")

            try:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()

                raw_json = response.json()

                items = []
                if isinstance(raw_json, list):
                    items = raw_json
                elif isinstance(raw_json, dict):
                    for key in ("items", "data", "results", "users"):
                        maybe = raw_json.get(key)
                        if isinstance(maybe, list):
                            items = maybe
                            break

                if not items:
                    logger.debug("No more users found (empty payload), stopping pagination")
                    break

                if logger.isEnabledFor(logging.DEBUG):
                    first_user = items[0]
                    if isinstance(first_user, dict):
                        keys_preview = list(first_user.keys())
                        logger.debug(f"First user object keys: {keys_preview}")
                        logger.debug(
                            f"First user ID candidates: id={first_user.get('id')}, user_id={first_user.get('user_id')}, clerk_user_id={first_user.get('clerk_user_id')}"
                        )

                def _extract_id(u: dict[str, Any]) -> str | None:
                    if not isinstance(u, dict):
                        return None
                    return u.get("id") or u.get("user_id") or u.get("clerk_user_id")

                user_ids = [uid for uid in (_extract_id(u) for u in items) if uid]

                if not user_ids:
                    preview = items[:2] if isinstance(items, list) else 'empty'
                    logger.warning(f"No valid user IDs found in response. Users data: {preview}")
                    break

                logger.info(f"Fetched {len(user_ids)} active users (page {pages_yielded + 1})")
                yield user_ids

                pages_yielded += 1
                skip += page_size

                if len(items) < page_size:
                    logger.debug("Received fewer users than requested, reached end of data")
                    break

            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error fetching users: {e.response.status_code} - {e.response.text}")
                raise
            except httpx.RequestError as e:
                logger.error(f"Request error fetching users: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error fetching users: {e}")
                raise
