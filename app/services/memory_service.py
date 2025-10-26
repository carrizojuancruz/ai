from __future__ import annotations

import logging
from typing import Any

from botocore.exceptions import ClientError

from app.core.config import config
from app.services.memory.store_factory import create_s3_vectors_store_from_env

logger = logging.getLogger(__name__)


class MemoryService:
    """Service for handling memory operations with S3 Vectors."""

    VALID_MEMORY_TYPES = ["semantic", "episodic"]

    MAX_SEARCH_TOPK = 100
    MAX_LIST_RESULTS = 500
    BATCH_DELETE_SIZE = 100

    def __init__(self) -> None:
        """Initialize the memory service."""
        self._validate_config()
        self._store = None

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

    def _get_store(self):
        """Get or create S3 store instance (lazy loading)."""
        if self._store is None:
            self._store = create_s3_vectors_store_from_env()
        return self._store

    def _get_namespace(self, user_id: str, memory_type: str) -> tuple[str, str]:
        """Create namespace tuple for user and memory type."""
        return (user_id, memory_type)

    def _map_value_fields(self, item: Any) -> dict[str, Any]:
        """Map Item fields to value DTO format."""
        value_dto = dict(item.value)

        value_dto["updated_at"] = value_dto.pop("last_accessed", None)
        value_dto["last_accessed"] = value_dto.pop("last_used_at", None)
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
            all_items = self._get_store().search(
                namespace,
                query=search,
                limit=self.MAX_SEARCH_TOPK,
            )
        else:
            all_items = self._get_store().list_by_namespace(
                namespace,
                return_metadata=True,
                max_results=self.MAX_LIST_RESULTS,
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

        if "last_accessed" in value:
            value["updated_at"] = value.pop("last_accessed")
        if "last_used_at" in value:
            value["last_accessed"] = value.pop("last_used_at")

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

        store = self._get_store()
        namespace = self._get_namespace(user_id, memory_type)

        item = store.get(namespace, memory_key)

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

        store = self._get_store()
        namespace = self._get_namespace(user_id, memory_type)

        try:
            store.delete(namespace, memory_key)
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

        store = self._get_store()
        namespace = self._get_namespace(user_id, memory_type)

        all_memories = store.list_by_namespace(
            namespace,
            return_metadata=True,
            max_results=self.MAX_LIST_RESULTS,
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
        result = store.batch_delete_by_keys(
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


memory_service = MemoryService()
