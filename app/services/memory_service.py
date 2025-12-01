from __future__ import annotations

import logging
from typing import Any

from botocore.exceptions import ClientError

from app.core.config import config
from app.services.memory.store_factory import create_s3_vectors_store_from_env
from app.repositories.session_store import get_session_store

logger = logging.getLogger(__name__)


class MemoryService:
    """Service for handling memory operations with S3 Vectors."""

    VALID_MEMORY_TYPES = ["semantic", "episodic"]

    MAX_SEARCH_TOPK = 100
    BATCH_DELETE_SIZE = 100

    def __init__(self) -> None:
        """Initialize the memory service."""
        self._validate_config()
        self._store = create_s3_vectors_store_from_env()

    def _validate_config(self) -> None:
        """Validate S3 configuration for memory service."""
        required_vars = {
            "S3V_BUCKET": config.S3V_BUCKET,
            "S3V_INDEX_MEMORY": config.S3V_INDEX_MEMORY,
            "AWS_REGION": config.get_aws_region(),
        }
        missing = [name for name, value in required_vars.items() if not value]
        if missing:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    def _validate_memory_type(self, memory_type: str) -> None:
        """Validate memory type is supported."""
        if memory_type not in self.VALID_MEMORY_TYPES:
            raise ValueError(f"memory_type must be one of: {', '.join(self.VALID_MEMORY_TYPES)}")

    def _get_namespace(self, user_id: str, memory_type: str) -> tuple[str, str]:
        """Create namespace tuple for user and memory type."""
        return (user_id, memory_type)

    def _get_wildcard_namespace(self, memory_type: str | None = None) -> tuple[None, str | None]:
        """Create wildcard namespace for querying across all users."""
        return (None, memory_type)

    def _get_limit(self, memory_type: str) -> int:
        """Get memory limit for given type."""
        if memory_type == "semantic":
            return config.MEMORY_SEMANTIC_MAX_LIMIT
        elif memory_type == "episodic":
            return config.MEMORY_EPISODIC_MAX_LIMIT
        else:
            raise ValueError(f"Unknown memory_type: {memory_type}")

    def _is_at_limit(self, user_id: str, memory_type: str) -> bool:
        """Check if user is at or over memory limit."""
        count = self.count_memories(user_id, memory_type)
        limit = self._get_limit(memory_type)
        return count >= limit

    async def initialize_memory_counters(
        self,
        user_id: str,
        thread_id: str | None = None,
    ) -> dict[str, int]:
        """Initialize cached memory counters for a conversation session."""
        try:
            sem = self.count_memories(user_id, "semantic")
            epi = self.count_memories(user_id, "episodic")
            store = get_session_store()
            await store.set_memory_counter(thread_id, "semantic", sem)
            await store.set_memory_counter(thread_id, "episodic", epi)
            return {"semantic": sem, "episodic": epi}
        except Exception:
            logger.exception("memory_counters.init.error: user_id=%s", user_id)
            return {"semantic": 0, "episodic": 0}

    async def get_memory_count_cached(
        self,
        user_id: str,
        memory_type: str,
        thread_id: str | None = None,
    ) -> int:
        """Get memory count using session cache; fallback to S3 when missing."""
        self._validate_memory_type(memory_type)
        try:
            store = get_session_store()
            cached = await store.get_memory_counter(thread_id, memory_type)
            if isinstance(cached, int):
                return cached
            actual = self.count_memories(user_id, memory_type)
            await store.set_memory_counter(thread_id, memory_type, actual)
            return actual
        except Exception:
            logger.exception("memory_counters.get.error: user_id=%s type=%s", user_id, memory_type)
            return self.count_memories(user_id, memory_type)

    async def increment_memory_counter(
        self,
        user_id: str,
        memory_type: str,
        thread_id: str | None = None,
        delta: int = 1,
    ) -> int:
        """Increment/decrement cached counter; no-op if cache missing."""
        self._validate_memory_type(memory_type)
        try:
            store = get_session_store()
            new_val = await store.increment_memory_counter(thread_id, memory_type, delta)
            if new_val is None:
                actual = self.count_memories(user_id, memory_type)
                await store.set_memory_counter(thread_id, memory_type, max(0, actual + delta))
                return max(0, actual + delta)
            return new_val
        except Exception:
            logger.exception("memory_counters.inc.error: user_id=%s type=%s", user_id, memory_type)
            return await self.get_memory_count_cached(user_id, memory_type, thread_id)

    async def invalidate_memory_counter(
        self,
        user_id: str,
        memory_type: str,
        thread_id: str | None = None,
    ) -> None:
        """Invalidate cached counter in session."""
        try:
            store = get_session_store()
            await store.invalidate_memory_counter(thread_id, memory_type)
        except Exception:
            logger.exception("memory_counters.invalidate.error: user_id=%s type=%s", user_id, memory_type)

    def _map_value_fields(self, item: Any) -> dict[str, Any]:
        """Map Item fields to value DTO format while preserving last_used_at.

        - Expose updated_at derived from last_accessed (keep last_accessed if present)
        - Preserve last_used_at as-is (do not remap)
        """
        value_dto = dict(item.value)
        if "last_accessed" in value_dto and "updated_at" not in value_dto:
            value_dto["updated_at"] = value_dto["last_accessed"]
        if "last_used_at" in value_dto:
            value_dto["last_accessed"] = value_dto["last_used_at"]
        return value_dto

    def get_memories(
        self,
        user_id: str,
        memory_type: str = "semantic",
        *,
        search: str | None = None,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """List memories for a user with optional semantic search and category filter.

        If search is provided, uses vector similarity (semantic search).
        Otherwise, lists all memories and applies category filter if provided.
        """
        self._validate_memory_type(memory_type)

        namespace = self._get_namespace(user_id, memory_type)

        if search:
            all_items = self._store.search(
                namespace,
                query=search,
                limit=self.MAX_SEARCH_TOPK,
            )
        else:
            all_items = self._store.list_by_namespace(
                namespace,
                return_metadata=True,
            )

        filtered_items = self._apply_category_filter(all_items, category)

        results = self._transform_items_to_response(filtered_items)

        return results

    def _apply_category_filter(
        self,
        items: list[Any],
        category: str | None,
    ) -> list[Any]:
        """Apply category filter to memory items."""
        if not category:
            return items

        return [
            item for item in items
            if item.value.get("category") == category
        ]

    def _transform_items_to_response(
        self,
        items: list[Any],
    ) -> list[dict[str, Any]]:
        """Transform SearchItems to API response format."""
        return [self._transform_single_item(item) for item in items]

    def _transform_single_item(self, item: Any) -> dict[str, Any]:
        """Transform single SearchItem to response dict with field mapping."""
        value = item.value.copy()
        if "last_accessed" in value and "updated_at" not in value:
            value["updated_at"] = value["last_accessed"]
        if "last_used_at" in value:
            value["last_accessed"] = value["last_used_at"]

        return {
            "key": item.key,
            "namespace": item.namespace,
            "value": value,
            "score": None,
        }

    def get_memory_by_key(
        self,
        user_id: str,
        memory_key: str,
        memory_type: str = "semantic"
    ) -> dict[str, Any]:
        """Retrieve a single memory by its key.

        Args:
            user_id: User ID
            memory_key: Memory key to retrieve
            memory_type: Type of memory (semantic or episodic)

        Returns:
            Dictionary with memory data or error

        Raises:
            ValueError: If memory_type is invalid
            RuntimeError: If memory not found

        """
        self._validate_memory_type(memory_type)

        namespace = self._get_namespace(user_id, memory_type)

        item = self._store.get(namespace, memory_key)

        if not item:
            raise RuntimeError("Memory not found")

        return {
            "key": item.key,
            "namespace": list(item.namespace),
            "value": self._map_value_fields(item)
        }

    def delete_memory_by_key(
        self,
        user_id: str,
        memory_key: str,
        memory_type: str = "semantic"
    ) -> dict[str, Any]:
        """Delete a single memory by its key.

        Args:
            user_id: User ID
            memory_key: Memory key to delete
            memory_type: Type of memory (semantic or episodic)

        Returns:
            Dictionary with deletion result

        """
        self._validate_memory_type(memory_type)

        namespace = self._get_namespace(user_id, memory_type)

        try:
            self._store.delete(namespace, memory_key)
            return {
                "ok": True,
                "message": f"Memory {memory_key} deleted successfully",
                "key": memory_key
            }
        except ClientError as e:
            return {
                "ok": False,
                "message": f"Failed to delete memory due to AWS service error: {str(e)}",
                "key": memory_key
            }
        except AttributeError as e:
            return {
                "ok": False,
                "message": f"Failed to delete memory due to client configuration error: {str(e)}",
                "key": memory_key
            }
        except Exception as e:
            return {
                "ok": False,
                "message": f"Failed to delete memory due to unexpected error: {str(e)}",
                "key": memory_key
            }

    def delete_all_memories(
        self,
        user_id: str,
        memory_type: str = "semantic",
    ) -> dict[str, Any]:
        """Delete all memories for a user and type using efficient batch deletion.

        Args:
            user_id: The user ID whose memories should be deleted
            memory_type: Type of memories to delete (semantic or episodic)

        Returns:
            Dictionary with deletion results (ok, message, deleted_count, failed_count, total_found)

        """
        self._validate_memory_type(memory_type)

        namespace = self._get_namespace(user_id, memory_type)

        all_memories = self._store.list_by_namespace(
            namespace,
            return_metadata=True,
        )
        total_found = len(all_memories)

        if total_found == 0:
            return {
                "ok": True,
                "message": "No memories found to delete",
                "deleted_count": 0,
                "failed_count": 0,
                "total_found": 0,
            }

        memory_keys = [memory.key for memory in all_memories]
        result = self._store.batch_delete_by_keys(
            namespace=namespace,
            keys=memory_keys,
            batch_size=self.BATCH_DELETE_SIZE,
        )

        deleted_count = result["deleted_count"]
        failed_count = result["failed_count"]

        if failed_count == 0:
            message = f"Successfully deleted all {deleted_count} memories"
        elif deleted_count > 0:
            message = f"Partially successful: deleted {deleted_count}/{total_found} memories"
        else:
            message = "Failed to delete any memories"

        return {
            "ok": True,
            "message": message,
            "deleted_count": deleted_count,
            "failed_count": failed_count,
            "total_found": total_found,
        }

    def count_memories(self, user_id: str, memory_type: str = "semantic") -> int:
        """Count total memories for user and type."""
        self._validate_memory_type(memory_type)
        namespace = self._get_namespace(user_id, memory_type)

        try:
            items = self._store.list_by_namespace(
                namespace,
                return_metadata=True,
            )
            return len(items)
        except Exception as e:
            logger.exception(
                "memory_service.count.error: user_id=%s type=%s error=%s",
                user_id, memory_type, str(e)
            )
            return 0

    def find_oldest_memory(
        self,
        user_id: str,
        memory_type: str
    ) -> tuple[str, dict[str, Any]] | None:
        """Find the oldest memory by last_accessed."""
        self._validate_memory_type(memory_type)
        namespace = self._get_namespace(user_id, memory_type)

        try:
            items = self._store.list_by_namespace(
                namespace,
                return_metadata=True,
            )

            if not items:
                logger.warning(
                    "memory_service.no_memories: user_id=%s type=%s",
                    user_id, memory_type
                )
                return None

            items.sort(key=lambda item: item.value.get("last_accessed") or item.value.get("created_at", ""))
            oldest = items[0]

            logger.info(
                "memory_service.found_oldest: user_id=%s type=%s key=%s last_accessed=%s",
                user_id, memory_type, oldest.key, oldest.value.get("last_accessed")
            )

            return (oldest.key, dict(oldest.value))

        except Exception:
            logger.exception(
                "memory_service.find_oldest.error: user_id=%s type=%s",
                user_id, memory_type
            )
            return None

    def _check_limit_and_get_oldest(
        self,
        user_id: str,
        memory_type: str
    ) -> tuple[bool, tuple[str, dict[str, Any]] | None]:
        """Check if at limit and return oldest memory."""
        self._validate_memory_type(memory_type)
        namespace = self._get_namespace(user_id, memory_type)
        limit = self._get_limit(memory_type)

        try:
            items = self._store.list_by_namespace(
                namespace,
                return_metadata=True,
            )

            count = len(items)
            is_at_limit = count >= limit

            if not is_at_limit or not items:
                return (is_at_limit, None)

            items.sort(key=lambda item: item.value.get("last_accessed") or item.value.get("created_at", ""))
            oldest = items[0]

            logger.info(
                "memory_service.check_limit: user_id=%s type=%s count=%d limit=%d oldest_key=%s",
                user_id, memory_type, count, limit, oldest.key
            )

            return (True, (oldest.key, dict(oldest.value)))

        except Exception:
            logger.exception(
                "memory_service.check_limit.error: user_id=%s type=%s",
                user_id, memory_type
            )
            return (False, None)

    def delete_memory(self, user_id: str, memory_type: str, key: str) -> bool:
        """Delete a specific memory."""
        self._validate_memory_type(memory_type)
        namespace = self._get_namespace(user_id, memory_type)

        try:
            self._store.delete(namespace, key)
            logger.info(
                "memory_service.deleted: user_id=%s type=%s key=%s",
                user_id, memory_type, key
            )
            return True
        except Exception:
            logger.exception(
                "memory_service.delete.error: user_id=%s type=%s key=%s",
                user_id, memory_type, key
            )
            return False

    async def create_memory(
        self,
        user_id: str,
        memory_type: str,
        key: str,
        value: dict[str, Any],
        *,
        index: list[str] | None = None,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new memory with cached limit enforcement when available."""
        self._validate_memory_type(memory_type)
        namespace = self._get_namespace(user_id, memory_type)
        index_fields = index or ["summary"]
        try:
            if thread_id:
                current = await self.get_memory_count_cached(user_id, memory_type, thread_id)
                limit = self._get_limit(memory_type)
                if current >= limit:
                    is_at_limit, oldest = self._check_limit_and_get_oldest(user_id, memory_type)
                    if is_at_limit and oldest:
                        old_key, _ = oldest
                        self._store.delete(namespace, old_key)
            else:
                is_at_limit, oldest = self._check_limit_and_get_oldest(user_id, memory_type)
                if is_at_limit and oldest:
                    old_key, _ = oldest
                    self._store.delete(namespace, old_key)
        except Exception:
            logger.exception("memory.create.limit_check.error: user_id=%s type=%s", user_id, memory_type)

        self._store.put(namespace, key, value, index=index_fields)
        try:
            if thread_id:
                await self.increment_memory_counter(user_id, memory_type, thread_id, delta=1)
        except Exception:
            logger.debug("memory.create.counter_inc.skip: user_id=%s type=%s", user_id, memory_type)
        return {"ok": True, "key": key, "value": value}

    def get_all_memories(
        self,
        memory_type: str | None = None,
        *,
        category: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Get all memories across all users, optionally filtered by memory type."""
        if memory_type:
            self._validate_memory_type(memory_type)

        all_items = []

        try:
            namespace = self._get_wildcard_namespace(memory_type)
            items = self._store.list_by_namespace(
                namespace,
                return_metadata=True,
                limit=limit,
            )

            filtered_items = self._apply_category_filter(items, category)

            for item in filtered_items:
                all_items.append(self._transform_single_item(item))

            return all_items

        except Exception as e:
            logger.error(f"Failed to get all memories: {e}", exc_info=True)
            return []

    def list_supervisor_routing_memories(self) -> list[dict[str, Any]]:
        """List all supervisor procedural routing memories.

        Returns:
            List of dicts with keys: key, summary, category

        """
        try:
            namespace = ("system", "supervisor_procedural")
            items = self._store.list_by_namespace(
                namespace,
                return_metadata=True,
            )
            results = []
            for item in items:
                value = getattr(item, "value", {}) or {}
                results.append({
                    "key": getattr(item, "key", ""),
                    "summary": value.get("summary", ""),
                    "category": value.get("category", "Routing")
                })

            logger.info(f"Listed {len(results)} supervisor routing memories")
            return results

        except Exception as e:
            logger.error(f"Failed to list supervisor routing memories: {e}", exc_info=True)
            raise


memory_service = MemoryService()
