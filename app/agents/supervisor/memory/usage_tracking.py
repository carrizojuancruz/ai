"""Memory usage tracking for semantic memories."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from langgraph.store.base import BaseStore

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


async def _update_single_memory(
    store: BaseStore,
    namespace: tuple[str, str],
    key: str,
    timestamp: str,
    user_id: str,
) -> bool:
    try:
        item = await store.aget(namespace, key)

        if not item:
            logger.debug(
                "memory_usage_tracking.memory_not_found key=%s user_id=%s",
                key,
                user_id
            )
            return False

        memory_item = item[0] if isinstance(item, list) else item
        current_value = memory_item.value

        updated_value = dict(current_value)
        updated_value.pop("last_used_at", None)
        updated_value["last_used_at"] = timestamp

        await store.aput(namespace, key, updated_value, index=False)

        logger.debug(
            "memory_usage_tracking.updated key=%s timestamp=%s",
            key,
            timestamp
        )
        return True

    except Exception as e:
        logger.warning(
            "memory_usage_tracking.update_failed key=%s user_id=%s error=%s",
            key,
            user_id,
            str(e)
        )
        return False


async def _update_last_used_async(
    store: BaseStore,
    user_id: str,
    memory_keys: list[str],
) -> None:
    """Update last_used_at timestamp for multiple memories."""
    if not memory_keys:
        return

    timestamp = _utc_now_iso()
    namespace = (user_id, "semantic")

    results = await asyncio.gather(
        *[
            _update_single_memory(store, namespace, key, timestamp, user_id)
            for key in memory_keys
        ],
        return_exceptions=True
    )

    success_count = sum(1 for r in results if r is True)
    error_count = sum(1 for r in results if isinstance(r, Exception))

    if error_count > 0:
        logger.warning(
            "memory_usage_tracking.batch_complete user_id=%s success=%d errors=%d",
            user_id,
            success_count,
            error_count
        )
    else:
        logger.debug(
            "memory_usage_tracking.batch_complete user_id=%s success=%d",
            user_id,
            success_count
        )


def update_memory_usage_tracking(
    store: BaseStore,
    user_id: str,
    memory_items: list[Any],
) -> None:
    """Track memory usage by updating last_used_at timestamps in background."""
    try:
        memory_keys = [
            getattr(item, "key", None)
            for item in memory_items
            if hasattr(item, "key") and getattr(item, "key", None)
        ]

        if not memory_keys:
            return

        task = asyncio.create_task(
            _update_last_used_async(store, user_id, memory_keys),
            name=f"memory_usage_tracking_{user_id}"
        )

        def _log_task_exception(t: asyncio.Task) -> None:
            try:
                t.result()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(
                    "memory_usage_tracking.task_failed user_id=%s error=%s",
                    user_id,
                    str(e),
                    exc_info=e
                )

        task.add_done_callback(_log_task_exception)

        logger.debug(
            "memory_usage_tracking.task_created user_id=%s count=%d",
            user_id,
            len(memory_keys)
        )
    except Exception as e:
        logger.warning(
            "memory_usage_tracking.failed user_id=%s error=%s",
            user_id if user_id else "unknown",
            str(e)
        )

