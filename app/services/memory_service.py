from __future__ import annotations

from typing import Any, Optional

from botocore.exceptions import ClientError

from app.core.config import config
from app.services.memory.store_factory import create_s3_vectors_store_from_env


class MemoryService:
    """Service for handling memory operations with S3 Vectors."""

    # Query constants for different memory types
    SEMANTIC_QUERY = "profile"
    EPISODIC_QUERY = "recent conversation"

    # S3 Vectors limits and configuration
    MAX_TOPK = 30  # S3 Vectors maximum topK limit

    # Valid memory types
    VALID_MEMORY_TYPES = ["semantic", "episodic"]

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

    def _get_query_for_type(self, memory_type: str) -> str:
        """Get the appropriate query string for memory type."""
        return self.SEMANTIC_QUERY if memory_type == "semantic" else self.EPISODIC_QUERY

    def get_memories(
        self,
        user_id: str,
        memory_type: str = "semantic",
        category: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Retrieve memories for a user with optional filtering.

        Args:
            user_id: User ID to retrieve memories for
            memory_type: Type of memories (semantic or episodic)
            category: Optional category filter
            search: Optional text search within memory summaries
            limit: Maximum number of items to return
            offset: Offset for pagination

        Returns:
            Dictionary with ok status, count, and items list

        """
        self._validate_memory_type(memory_type)

        store = self._get_store()
        namespace = self._get_namespace(user_id, memory_type)
        broad_query = self._get_query_for_type(memory_type)

        user_filter = {"category": category} if category else None

        # Collect all memories using batching approach
        # S3 Vectors limits topK to maximum of MAX_TOPK, so we batch accordingly
        all_items = []
        batch_offset = offset
        batch_limit = min(self.MAX_TOPK, limit)

        while len(all_items) < limit:
            remaining_needed = limit - len(all_items)
            current_batch_limit = min(batch_limit, remaining_needed)

            batch_items = store.search(
                namespace,
                query=broad_query,
                filter=user_filter,
                limit=current_batch_limit,
                offset=batch_offset
            )

            if not batch_items:
                break

            all_items.extend(batch_items)
            batch_offset += current_batch_limit

            if len(batch_items) < current_batch_limit:
                break

        filtered_items = []
        for item in all_items:
            if search:
                summary = str((item.value or {}).get("summary", "")).lower()
                if search.lower() not in summary:
                    continue
            filtered_items.append(item)

        paginated_items = filtered_items[:limit]

        results = []
        for item in paginated_items:
            results.append({
                "key": item.key,
                "namespace": list(item.namespace),
                "created_at": item.created_at,
                "updated_at": item.updated_at,
                "score": float(item.score or 0.0),
                "value": item.value
            })

        return {
            "ok": True,
            "count": len(results),
            "items": results
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
        broad_query = self._get_query_for_type(memory_type)
        user_filter = {"doc_key": memory_key}

        items = store.search(
            namespace,
            query=broad_query,
            filter=user_filter,
            limit=1
        )

        if not items:
            raise RuntimeError("Memory not found")

        item = items[0]

        return {
            "key": item.key,
            "namespace": list(item.namespace),
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "value": item.value
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
        memory_type: str = "semantic"
    ) -> dict[str, Any]:
        """Delete ALL memories for a user and type.

        Args:
            user_id: User ID
            memory_type: Type of memories to delete (semantic or episodic)

        Returns:
            Dictionary with deletion statistics

        """
        self._validate_memory_type(memory_type)

        store = self._get_store()
        namespace = self._get_namespace(user_id, memory_type)

        all_keys = []
        offset = 0
        batch_limit = self.MAX_TOPK

        query = self._get_query_for_type(memory_type)

        while True:
            items = store.search(namespace, query=query, filter=None, limit=batch_limit, offset=offset)
            batch_keys = [item.key for item in items]

            if not batch_keys:
                break

            all_keys.extend(batch_keys)
            offset += batch_limit

            if len(batch_keys) < batch_limit:
                break

        if not all_keys:
            return {
                "ok": True,
                "message": "No memories found to delete",
                "deleted_count": 0,
                "total_found": 0
            }

        deleted_count = 0
        failed_count = 0

        for key in all_keys:
            try:
                store.delete(namespace, key)
                deleted_count += 1
            except (ClientError, AttributeError):
                failed_count += 1

        return {
            "ok": True,
            "message": f"Deleted {deleted_count} memories, {failed_count} failed",
            "deleted_count": deleted_count,
            "failed_count": failed_count,
            "total_found": len(all_keys)
        }


# Create a singleton instance
memory_service = MemoryService()
