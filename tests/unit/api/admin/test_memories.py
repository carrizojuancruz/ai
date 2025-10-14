"""Unit tests for app.api.admin.memories module.

Tests cover:
- Pydantic model validation and datetime conversion
- GET /admin/memories/{user_id} - list memories with filters
- GET /admin/memories/{user_id}/{memory_key} - get single memory
- DELETE /admin/memories/{user_id}/{memory_key} - delete single memory
- DELETE /admin/memories/{user_id} - delete all memories with confirmation
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException

from app.api.admin.memories import (
    MemoryDeleteResponse,
    MemoryGetResponse,
    MemoryItem,
    MemorySearchResponse,
    delete_all_memories,
    delete_memory_by_key,
    get_memories,
    get_memory_by_key,
)


class TestMemoryItemModel:
    """Test cases for MemoryItem Pydantic model."""

    def test_memory_item_with_all_fields(self):
        """Test MemoryItem creation with all fields."""
        item = MemoryItem(
            key="test_key",
            namespace=["user", "123", "semantic"],
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-02T00:00:00",
            score=0.95,
            value={"summary": "Test memory", "category": "Finance"},
        )

        assert item.key == "test_key"
        assert item.namespace == ["user", "123", "semantic"]
        assert item.created_at == "2024-01-01T00:00:00"
        assert item.updated_at == "2024-01-02T00:00:00"
        assert item.score == 0.95
        assert item.value == {"summary": "Test memory", "category": "Finance"}

    def test_memory_item_converts_datetime_to_string(self):
        """Test that datetime objects are converted to ISO strings."""
        dt = datetime(2024, 1, 1, 12, 30, 45)
        item = MemoryItem(
            key="test_key",
            namespace=["user", "123"],
            created_at=dt,
            updated_at=dt,
            value={"test": "data"},
        )

        assert isinstance(item.created_at, str)
        assert item.created_at == "2024-01-01T12:30:45"
        assert isinstance(item.updated_at, str)
        assert item.updated_at == "2024-01-01T12:30:45"

    def test_memory_item_with_optional_fields_none(self):
        """Test MemoryItem with optional fields as None."""
        item = MemoryItem(
            key="test_key",
            namespace=["user", "123"],
            created_at=None,
            updated_at=None,
            score=None,
            value={},
        )

        assert item.created_at is None
        assert item.updated_at is None
        assert item.score is None

    def test_memory_item_minimal_required_fields(self):
        """Test MemoryItem with only required fields."""
        item = MemoryItem(key="key", namespace=["ns"], value={"data": "value"})

        assert item.key == "key"
        assert item.namespace == ["ns"]
        assert item.value == {"data": "value"}


class TestMemorySearchResponseModel:
    """Test cases for MemorySearchResponse Pydantic model."""

    def test_memory_search_response_with_items(self):
        """Test MemorySearchResponse with items."""
        items = [
            MemoryItem(key="key1", namespace=["ns"], value={"a": 1}),
            MemoryItem(key="key2", namespace=["ns"], value={"b": 2}),
        ]
        response = MemorySearchResponse(ok=True, count=2, items=items)

        assert response.ok is True
        assert response.count == 2
        assert len(response.items) == 2
        assert response.items[0].key == "key1"
        assert response.items[1].key == "key2"

    def test_memory_search_response_empty_items(self):
        """Test MemorySearchResponse with empty items list."""
        response = MemorySearchResponse(ok=True, count=0, items=[])

        assert response.ok is True
        assert response.count == 0
        assert response.items == []


class TestMemoryGetResponseModel:
    """Test cases for MemoryGetResponse Pydantic model."""

    def test_memory_get_response_with_all_fields(self):
        """Test MemoryGetResponse with all fields."""
        response = MemoryGetResponse(
            key="test_key",
            namespace=["user", "123"],
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-02T00:00:00",
            value={"summary": "Test"},
        )

        assert response.key == "test_key"
        assert response.namespace == ["user", "123"]
        assert response.created_at == "2024-01-01T00:00:00"
        assert response.updated_at == "2024-01-02T00:00:00"
        assert response.value == {"summary": "Test"}

    def test_memory_get_response_converts_datetime(self):
        """Test datetime conversion in MemoryGetResponse."""
        dt = datetime(2024, 1, 1, 10, 0, 0)
        response = MemoryGetResponse(
            key="key", namespace=["ns"], created_at=dt, updated_at=dt, value={}
        )

        assert response.created_at == "2024-01-01T10:00:00"
        assert response.updated_at == "2024-01-01T10:00:00"


class TestMemoryDeleteResponseModel:
    """Test cases for MemoryDeleteResponse Pydantic model."""

    def test_memory_delete_response_single_deletion(self):
        """Test MemoryDeleteResponse for single memory deletion."""
        response = MemoryDeleteResponse(
            ok=True, message="Memory deleted successfully", key="deleted_key"
        )

        assert response.ok is True
        assert response.message == "Memory deleted successfully"
        assert response.key == "deleted_key"
        assert response.deleted_count is None
        assert response.failed_count is None
        assert response.total_found is None

    def test_memory_delete_response_bulk_deletion(self):
        """Test MemoryDeleteResponse for bulk deletion."""
        response = MemoryDeleteResponse(
            ok=True,
            message="Bulk deletion completed",
            deleted_count=10,
            failed_count=2,
            total_found=12,
        )

        assert response.ok is True
        assert response.message == "Bulk deletion completed"
        assert response.deleted_count == 10
        assert response.failed_count == 2
        assert response.total_found == 12


class TestGetMemoriesEndpoint:
    """Test cases for GET /admin/memories/{user_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_memories_success_with_defaults(self):
        """Test successful memory retrieval with default parameters."""
        mock_result = {
            "ok": True,
            "count": 2,
            "items": [
                {
                    "key": "key1",
                    "namespace": ["user", "123", "semantic"],
                    "value": {"summary": "Memory 1"},
                },
                {
                    "key": "key2",
                    "namespace": ["user", "123", "semantic"],
                    "value": {"summary": "Memory 2"},
                },
            ],
        }

        with patch("app.api.admin.memories.memory_service") as mock_service:
            mock_service.get_memories.return_value = mock_result

            result = await get_memories(
                user_id="user-123",
                memory_type="semantic",
                category=None,
                search=None,
                limit=50,
                offset=0,
            )

            assert result.ok is True
            assert result.count == 2
            assert len(result.items) == 2
            assert result.items[0].key == "key1"
            assert result.items[1].key == "key2"

            mock_service.get_memories.assert_called_once_with(
                user_id="user-123",
                memory_type="semantic",
                category=None,
                search=None,
                limit=50,
                offset=0,
            )

    @pytest.mark.asyncio
    async def test_get_memories_with_category_filter(self):
        """Test memory retrieval with category filter."""
        mock_result = {
            "ok": True,
            "count": 1,
            "items": [
                {
                    "key": "key1",
                    "namespace": ["user", "123"],
                    "value": {"summary": "Finance memory", "category": "Finance"},
                }
            ],
        }

        with patch("app.api.admin.memories.memory_service") as mock_service:
            mock_service.get_memories.return_value = mock_result

            result = await get_memories(
                user_id="user-123",
                memory_type="semantic",
                category="Finance",
                search=None,
                limit=50,
                offset=0,
            )

            assert result.ok is True
            assert result.count == 1
            mock_service.get_memories.assert_called_once()
            call_args = mock_service.get_memories.call_args[1]
            assert call_args["category"] == "Finance"

    @pytest.mark.asyncio
    async def test_get_memories_with_search_filter(self):
        """Test memory retrieval with search filter."""
        mock_result = {
            "ok": True,
            "count": 1,
            "items": [
                {
                    "key": "key1",
                    "namespace": ["user", "123"],
                    "value": {"summary": "Budget planning"},
                }
            ],
        }

        with patch("app.api.admin.memories.memory_service") as mock_service:
            mock_service.get_memories.return_value = mock_result

            result = await get_memories(
                user_id="user-123",
                memory_type="semantic",
                category=None,
                search="budget",
                limit=50,
                offset=0,
            )

            assert result.count == 1
            call_args = mock_service.get_memories.call_args[1]
            assert call_args["search"] == "budget"

    @pytest.mark.asyncio
    async def test_get_memories_with_pagination(self):
        """Test memory retrieval with custom limit and offset."""
        mock_result = {"ok": True, "count": 100, "items": []}

        with patch("app.api.admin.memories.memory_service") as mock_service:
            mock_service.get_memories.return_value = mock_result

            result = await get_memories(
                user_id="user-123",
                memory_type="semantic",
                category=None,
                search=None,
                limit=10,
                offset=20,
            )

            assert result.ok is True
            call_args = mock_service.get_memories.call_args[1]
            assert call_args["limit"] == 10
            assert call_args["offset"] == 20

    @pytest.mark.asyncio
    async def test_get_memories_episodic_type(self):
        """Test retrieving episodic memories."""
        mock_result = {
            "ok": True,
            "count": 1,
            "items": [
                {
                    "key": "conv_1",
                    "namespace": ["user", "123", "episodic"],
                    "value": {"conversation": "User asked about savings"},
                }
            ],
        }

        with patch("app.api.admin.memories.memory_service") as mock_service:
            mock_service.get_memories.return_value = mock_result

            result = await get_memories(
                user_id="user-123",
                memory_type="episodic",
                category=None,
                search=None,
                limit=50,
                offset=0,
            )

            assert result.ok is True
            call_args = mock_service.get_memories.call_args[1]
            assert call_args["memory_type"] == "episodic"

    @pytest.mark.asyncio
    async def test_get_memories_empty_result(self):
        """Test memory retrieval when no memories found."""
        mock_result = {"ok": True, "count": 0, "items": []}

        with patch("app.api.admin.memories.memory_service") as mock_service:
            mock_service.get_memories.return_value = mock_result

            result = await get_memories(
                user_id="user-999",
                memory_type="semantic",
                category=None,
                search=None,
                limit=50,
                offset=0,
            )

            assert result.ok is True
            assert result.count == 0
            assert result.items == []

    @pytest.mark.asyncio
    async def test_get_memories_value_error_raises_400(self):
        """Test that ValueError raises HTTPException with 400 status."""
        with patch("app.api.admin.memories.memory_service") as mock_service:
            mock_service.get_memories.side_effect = ValueError("Invalid memory type")

            with pytest.raises(HTTPException) as exc_info:
                await get_memories(
                    user_id="user-123",
                    memory_type="invalid",
                    category=None,
                    search=None,
                    limit=50,
                    offset=0,
                )

            assert exc_info.value.status_code == 400
            assert "Invalid memory type" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_memories_generic_exception_raises_500(self):
        """Test that generic exceptions raise HTTPException with 500 status."""
        with patch("app.api.admin.memories.memory_service") as mock_service:
            mock_service.get_memories.side_effect = Exception("Database connection error")

            with pytest.raises(HTTPException) as exc_info:
                await get_memories(
                    user_id="user-123",
                    memory_type="semantic",
                    category=None,
                    search=None,
                    limit=50,
                    offset=0,
                )

            assert exc_info.value.status_code == 500
            assert "Failed to retrieve memories" in str(exc_info.value.detail)


class TestGetMemoryByKeyEndpoint:
    """Test cases for GET /admin/memories/{user_id}/{memory_key} endpoint."""

    @pytest.mark.asyncio
    async def test_get_memory_by_key_success(self):
        """Test successful single memory retrieval."""
        mock_result = {
            "key": "memory_123",
            "namespace": ["user", "user-123", "semantic"],
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-02T00:00:00",
            "value": {"summary": "User prefers concise responses", "category": "Personal"},
        }

        with patch("app.api.admin.memories.memory_service") as mock_service:
            mock_service.get_memory_by_key.return_value = mock_result

            result = await get_memory_by_key(
                user_id="user-123", memory_key="memory_123", memory_type="semantic"
            )

            assert result.key == "memory_123"
            assert result.namespace == ["user", "user-123", "semantic"]
            assert result.value["summary"] == "User prefers concise responses"

            mock_service.get_memory_by_key.assert_called_once_with(
                user_id="user-123", memory_key="memory_123", memory_type="semantic"
            )

    @pytest.mark.asyncio
    async def test_get_memory_by_key_episodic(self):
        """Test retrieving episodic memory by key."""
        mock_result = {
            "key": "conv_456",
            "namespace": ["user", "user-123", "episodic"],
            "value": {"conversation_summary": "Discussed investment strategies"},
        }

        with patch("app.api.admin.memories.memory_service") as mock_service:
            mock_service.get_memory_by_key.return_value = mock_result

            result = await get_memory_by_key(
                user_id="user-123", memory_key="conv_456", memory_type="episodic"
            )

            assert result.key == "conv_456"
            call_args = mock_service.get_memory_by_key.call_args[1]
            assert call_args["memory_type"] == "episodic"

    @pytest.mark.asyncio
    async def test_get_memory_by_key_value_error_raises_400(self):
        """Test that ValueError raises 400 status code."""
        with patch("app.api.admin.memories.memory_service") as mock_service:
            mock_service.get_memory_by_key.side_effect = ValueError("Invalid memory type")

            with pytest.raises(HTTPException) as exc_info:
                await get_memory_by_key(
                    user_id="user-123", memory_key="key", memory_type="invalid"
                )

            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_get_memory_by_key_runtime_error_raises_404(self):
        """Test that RuntimeError (not found) raises 404 status code."""
        with patch("app.api.admin.memories.memory_service") as mock_service:
            mock_service.get_memory_by_key.side_effect = RuntimeError("Memory not found")

            with pytest.raises(HTTPException) as exc_info:
                await get_memory_by_key(
                    user_id="user-123", memory_key="nonexistent", memory_type="semantic"
                )

            assert exc_info.value.status_code == 404
            assert "Memory not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_memory_by_key_generic_exception_raises_500(self):
        """Test that generic exceptions raise 500 status code."""
        with patch("app.api.admin.memories.memory_service") as mock_service:
            mock_service.get_memory_by_key.side_effect = Exception("Unexpected error")

            with pytest.raises(HTTPException) as exc_info:
                await get_memory_by_key(
                    user_id="user-123", memory_key="key", memory_type="semantic"
                )

            assert exc_info.value.status_code == 500
            assert "Failed to retrieve memory" in str(exc_info.value.detail)


class TestDeleteMemoryByKeyEndpoint:
    """Test cases for DELETE /admin/memories/{user_id}/{memory_key} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_memory_by_key_success(self):
        """Test successful single memory deletion."""
        mock_result = {
            "ok": True,
            "message": "Memory deleted successfully",
            "key": "memory_123",
        }

        mock_fos_manager = Mock()
        mock_fos_manager.delete_nudges_by_memory_id = AsyncMock()

        with patch("app.api.admin.memories.memory_service") as mock_service:
            mock_service.delete_memory_by_key.return_value = mock_result

            result = await delete_memory_by_key(
                user_id="user-123",
                memory_key="memory_123",
                memory_type="semantic",
                fos_manager=mock_fos_manager,
            )

            assert result.ok is True
            assert result.message == "Memory deleted successfully"
            assert result.key == "memory_123"

            mock_service.delete_memory_by_key.assert_called_once_with(
                user_id="user-123", memory_key="memory_123", memory_type="semantic"
            )

            # Verify nudges were also deleted
            mock_fos_manager.delete_nudges_by_memory_id.assert_called_once_with("memory_123")

    @pytest.mark.asyncio
    async def test_delete_memory_by_key_without_fos_manager(self):
        """Test deletion without FOSNudgeManager (nudges not deleted)."""
        mock_result = {
            "ok": True,
            "message": "Memory deleted successfully",
            "key": "memory_123",
        }

        with patch("app.api.admin.memories.memory_service") as mock_service:
            mock_service.delete_memory_by_key.return_value = mock_result

            result = await delete_memory_by_key(
                user_id="user-123",
                memory_key="memory_123",
                memory_type="semantic",
                fos_manager=None,
            )

            assert result.ok is True
            mock_service.delete_memory_by_key.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_memory_by_key_nudge_deletion_fails_gracefully(self):
        """Test that nudge deletion failure doesn't affect memory deletion."""
        mock_result = {"ok": True, "message": "Memory deleted", "key": "memory_123"}

        mock_fos_manager = Mock()
        mock_fos_manager.delete_nudges_by_memory_id = AsyncMock(
            side_effect=Exception("Nudge service unavailable")
        )

        with (
            patch("app.api.admin.memories.memory_service") as mock_service,
            patch("app.api.admin.memories.logger") as mock_logger,
        ):
            mock_service.delete_memory_by_key.return_value = mock_result

            result = await delete_memory_by_key(
                user_id="user-123",
                memory_key="memory_123",
                memory_type="semantic",
                fos_manager=mock_fos_manager,
            )

            # Memory deletion should succeed
            assert result.ok is True

            # Error should be logged
            mock_logger.error.assert_called_once()
            assert "Failed to delete nudges" in str(mock_logger.error.call_args)

    @pytest.mark.asyncio
    async def test_delete_memory_by_key_value_error_raises_400(self):
        """Test that ValueError raises 400 status code."""
        with patch("app.api.admin.memories.memory_service") as mock_service:
            mock_service.delete_memory_by_key.side_effect = ValueError("Invalid memory type")

            with pytest.raises(HTTPException) as exc_info:
                await delete_memory_by_key(
                    user_id="user-123",
                    memory_key="key",
                    memory_type="invalid",
                    fos_manager=None,
                )

            assert exc_info.value.status_code == 400


class TestDeleteAllMemoriesEndpoint:
    """Test cases for DELETE /admin/memories/{user_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_all_memories_success(self):
        """Test successful bulk memory deletion."""
        mock_result = {
            "ok": True,
            "message": "All memories deleted",
            "deleted_count": 10,
            "failed_count": 0,
            "total_found": 10,
        }

        mock_fos_manager = Mock()
        mock_fos_manager.delete_nudges_by_user_id = AsyncMock()

        with patch("app.api.admin.memories.memory_service") as mock_service:
            mock_service.delete_all_memories.return_value = mock_result

            result = await delete_all_memories(
                user_id="user-123",
                memory_type="semantic",
                confirm=True,
                fos_manager=mock_fos_manager,
            )

            assert result.ok is True
            assert result.deleted_count == 10
            assert result.failed_count == 0
            assert result.total_found == 10

            mock_service.delete_all_memories.assert_called_once_with(
                user_id="user-123", memory_type="semantic"
            )

            # Verify nudges were also deleted
            mock_fos_manager.delete_nudges_by_user_id.assert_called_once_with("user-123")

    @pytest.mark.asyncio
    async def test_delete_all_memories_without_confirmation_raises_400(self):
        """Test that deletion without confirmation raises 400."""
        with pytest.raises(HTTPException) as exc_info:
            await delete_all_memories(
                user_id="user-123",
                memory_type="semantic",
                confirm=False,
                fos_manager=None,
            )

        assert exc_info.value.status_code == 400
        assert "not confirmed" in str(exc_info.value.detail).lower()
        assert "confirm=true" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_delete_all_memories_without_fos_manager(self):
        """Test bulk deletion without FOSNudgeManager."""
        mock_result = {
            "ok": True,
            "message": "Memories deleted",
            "deleted_count": 5,
            "failed_count": 0,
            "total_found": 5,
        }

        with patch("app.api.admin.memories.memory_service") as mock_service:
            mock_service.delete_all_memories.return_value = mock_result

            result = await delete_all_memories(
                user_id="user-123", memory_type="semantic", confirm=True, fos_manager=None
            )

            assert result.ok is True
            assert result.deleted_count == 5

    @pytest.mark.asyncio
    async def test_delete_all_memories_nudge_deletion_fails_gracefully(self):
        """Test that nudge deletion failure is logged but doesn't fail deletion."""
        mock_result = {
            "ok": True,
            "message": "Memories deleted",
            "deleted_count": 3,
            "failed_count": 0,
            "total_found": 3,
        }

        mock_fos_manager = Mock()
        mock_fos_manager.delete_nudges_by_user_id = AsyncMock(
            side_effect=Exception("Nudge service error")
        )

        with (
            patch("app.api.admin.memories.memory_service") as mock_service,
            patch("app.api.admin.memories.logger") as mock_logger,
        ):
            mock_service.delete_all_memories.return_value = mock_result

            result = await delete_all_memories(
                user_id="user-123",
                memory_type="semantic",
                confirm=True,
                fos_manager=mock_fos_manager,
            )

            # Deletion should succeed
            assert result.ok is True

            # Error should be logged
            mock_logger.error.assert_called_once()
            assert "Failed to delete nudges" in str(mock_logger.error.call_args)

    @pytest.mark.asyncio
    async def test_delete_all_memories_value_error_raises_400(self):
        """Test that ValueError raises 400 status code."""
        with patch("app.api.admin.memories.memory_service") as mock_service:
            mock_service.delete_all_memories.side_effect = ValueError("Invalid memory type")

            with pytest.raises(HTTPException) as exc_info:
                await delete_all_memories(
                    user_id="user-123",
                    memory_type="invalid",
                    confirm=True,
                    fos_manager=None,
                )

            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_all_memories_generic_exception_raises_500(self):
        """Test that generic exceptions raise 500 status code."""
        with patch("app.api.admin.memories.memory_service") as mock_service:
            mock_service.delete_all_memories.side_effect = Exception("Database error")

            with pytest.raises(HTTPException) as exc_info:
                await delete_all_memories(
                    user_id="user-123",
                    memory_type="semantic",
                    confirm=True,
                    fos_manager=None,
                )

            assert exc_info.value.status_code == 500
            assert "Failed to delete memories" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_delete_all_memories_episodic_type(self):
        """Test bulk deletion of episodic memories."""
        mock_result = {
            "ok": True,
            "message": "Episodic memories deleted",
            "deleted_count": 7,
            "failed_count": 1,
            "total_found": 8,
        }

        with patch("app.api.admin.memories.memory_service") as mock_service:
            mock_service.delete_all_memories.return_value = mock_result

            result = await delete_all_memories(
                user_id="user-123", memory_type="episodic", confirm=True, fos_manager=None
            )

            assert result.ok is True
            call_args = mock_service.delete_all_memories.call_args[1]
            assert call_args["memory_type"] == "episodic"
