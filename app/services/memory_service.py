from __future__ import annotations

from typing import Any, List, Optional

from app.core.config import config
from app.services.memory.store_factory import create_s3_vectors_store_from_env


class MemoryService:
    """Service for handling memory operations with S3 Vectors."""

    def __init__(self) -> None:
        """Initialize the memory service."""
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate S3 configuration."""
        missing = config.validate_required_s3_vars()
        if missing:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    def get_memories(
        self,
        user_id: str,
        memory_type: str = "semantic",
        category: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        Retrieve memories for a user with optional filtering.

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
        if memory_type not in ["semantic", "episodic"]:
            raise ValueError("memory_type must be 'semantic' or 'episodic'")

        store = create_s3_vectors_store_from_env()
        namespace = (user_id, memory_type)

        broad_query = "profile" if memory_type == "semantic" else "recent conversation"

        user_filter = {"category": category} if category else None

        # Collect all memories using batching approach
        # S3 Vectors limits topK to maximum of 30, so we batch accordingly
        all_items = []
        batch_offset = offset
        batch_limit = min(30, limit)  # S3 Vectors max topK is 30

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
        """
        Retrieve a single memory by its key.

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
        if memory_type not in ["semantic", "episodic"]:
            raise ValueError("memory_type must be 'semantic' or 'episodic'")

        store = create_s3_vectors_store_from_env()
        namespace = (user_id, memory_type)

        broad_query = "profile" if memory_type == "semantic" else "recent conversation"
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
        """
        Delete a single memory by its key.

        Args:
            user_id: User ID
            memory_key: Memory key to delete
            memory_type: Type of memory (semantic or episodic)

        Returns:
            Dictionary with deletion result
        """
        if memory_type not in ["semantic", "episodic"]:
            raise ValueError("memory_type must be 'semantic' or 'episodic'")

        store = create_s3_vectors_store_from_env()
        namespace = (user_id, memory_type)

        try:
            store.delete(namespace, memory_key)
            return {
                "ok": True,
                "message": f"Memory {memory_key} deleted successfully",
                "key": memory_key
            }
        except Exception as e:
            return {
                "ok": False,
                "message": f"Failed to delete memory: {str(e)}",
                "key": memory_key
            }

    def delete_all_memories(
        self,
        user_id: str,
        memory_type: str = "semantic"
    ) -> dict[str, Any]:
        """
        Delete ALL memories for a user and type.

        Args:
            user_id: User ID
            memory_type: Type of memories to delete (semantic or episodic)

        Returns:
            Dictionary with deletion statistics
        """
        if memory_type not in ["semantic", "episodic"]:
            raise ValueError("memory_type must be 'semantic' or 'episodic'")

        store = create_s3_vectors_store_from_env()
        namespace = (user_id, memory_type)

        all_keys = []
        offset = 0
        batch_limit = 30  # S3 Vectors max topK is 30

        query = "profile" if memory_type == "semantic" else "recent conversation"

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
            except Exception:
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
