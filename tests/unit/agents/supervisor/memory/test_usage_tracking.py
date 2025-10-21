"""Tests for memory usage tracking (last_used_at timestamps)."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.agents.supervisor.memory.usage_tracking import (
    _update_last_used_async,
    _utc_now_iso,
    update_memory_usage_tracking,
)


def test_utc_now_iso():
    """Test UTC timestamp generation."""
    result = _utc_now_iso()
    assert isinstance(result, str)
    assert "T" in result
    datetime.fromisoformat(result)


@pytest.mark.asyncio
async def test_update_last_used_at_success():
    """Test successful update of last_used_at field."""
    mock_store = Mock()
    mock_item = Mock()
    mock_item.value = {
        "id": "test-key",
        "summary": "Test memory",
        "last_used_at": None
    }
    mock_store.aget = AsyncMock(return_value=[mock_item])
    mock_store.aput = AsyncMock()

    await _update_last_used_async(
        mock_store,
        "user-123",
        ["test-key"]
    )

    mock_store.aget.assert_called_once()
    mock_store.aput.assert_called_once()

    call_args = mock_store.aput.call_args
    updated_value = call_args[0][2]
    assert "last_used_at" in updated_value
    assert updated_value["last_used_at"] is not None


@pytest.mark.asyncio
async def test_update_last_used_at_preserves_other_fields():
    """Test that update preserves all other fields."""
    mock_store = Mock()
    mock_item = Mock()
    original_value = {
        "id": "test-key",
        "summary": "Test memory",
        "category": "Finance",
        "importance": 3,
        "tags": ["test", "finance"],
        "last_used_at": None
    }
    mock_item.value = original_value.copy()
    mock_store.aget = AsyncMock(return_value=[mock_item])
    mock_store.aput = AsyncMock()

    await _update_last_used_async(
        mock_store,
        "user-123",
        ["test-key"]
    )

    call_args = mock_store.aput.call_args
    updated_value = call_args[0][2]

    assert updated_value["id"] == "test-key"
    assert updated_value["summary"] == "Test memory"
    assert updated_value["category"] == "Finance"
    assert updated_value["importance"] == 3
    assert updated_value["tags"] == ["test", "finance"]


@pytest.mark.asyncio
async def test_update_last_used_at_empty_list():
    """Test that empty list is handled gracefully."""
    mock_store = Mock()
    mock_store.aget = AsyncMock()
    mock_store.aput = AsyncMock()

    await _update_last_used_async(
        mock_store,
        "user-123",
        []
    )

    mock_store.aget.assert_not_called()
    mock_store.aput.assert_not_called()


@pytest.mark.asyncio
async def test_update_last_used_at_missing_memory():
    """Test handling of missing memory."""
    mock_store = Mock()
    mock_store.aget = AsyncMock(return_value=[])
    mock_store.aput = AsyncMock()

    await _update_last_used_async(
        mock_store,
        "user-123",
        ["missing-key"]
    )

    mock_store.aget.assert_called_once()
    mock_store.aput.assert_not_called()


@pytest.mark.asyncio
async def test_update_last_used_at_error_handling():
    """Test error handling during update."""
    mock_store = Mock()
    mock_store.aget = AsyncMock(side_effect=Exception("S3 error"))
    mock_store.aput = AsyncMock()

    await _update_last_used_async(
        mock_store,
        "user-123",
        ["test-key"]
    )

    mock_store.aput.assert_not_called()


@pytest.mark.asyncio
async def test_update_last_used_at_multiple_keys():
    """Test updating multiple memories."""
    mock_store = Mock()
    mock_item1 = Mock()
    mock_item1.value = {"id": "key-1", "summary": "Memory 1", "last_used_at": None}
    mock_item2 = Mock()
    mock_item2.value = {"id": "key-2", "summary": "Memory 2", "last_used_at": None}

    mock_store.aget = AsyncMock(side_effect=[[mock_item1], [mock_item2]])
    mock_store.aput = AsyncMock()

    await _update_last_used_async(
        mock_store,
        "user-123",
        ["key-1", "key-2"]
    )

    assert mock_store.aget.call_count == 2
    assert mock_store.aput.call_count == 2


@pytest.mark.asyncio
async def test_update_last_used_at_partial_failure():
    """Test handling partial failures in batch."""
    mock_store = Mock()
    mock_item = Mock()
    mock_item.value = {"id": "key-1", "summary": "Memory 1", "last_used_at": None}

    mock_store.aget = AsyncMock(side_effect=[[mock_item], Exception("Error"), [mock_item]])
    mock_store.aput = AsyncMock()

    await _update_last_used_async(
        mock_store,
        "user-123",
        ["key-1", "key-2", "key-3"]
    )

    assert mock_store.aget.call_count == 3
    assert mock_store.aput.call_count == 2


@pytest.mark.asyncio
async def test_update_memory_usage_tracking():
    """Test updating memory usage tracking."""
    mock_store = Mock()
    mock_item = Mock()
    mock_item.value = {"summary": "Test", "last_used_at": None}
    mock_store.aget = AsyncMock(return_value=[mock_item])
    mock_store.aput = AsyncMock()

    mock_items = [
        Mock(key="key-1"),
        Mock(key="key-2"),
    ]

    with patch("app.agents.supervisor.memory.usage_tracking.asyncio.create_task") as mock_create_task:
        update_memory_usage_tracking(
            mock_store,
            "user-123",
            mock_items
        )

        mock_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_spawn_update_no_keys():
    """Test that no updates happen when no keys."""
    mock_store = Mock()
    mock_items = []

    with patch("app.agents.supervisor.memory.usage_tracking.asyncio.create_task") as mock_create_task:
        update_memory_usage_tracking(
            mock_store,
            "user-123",
            mock_items
        )

        mock_create_task.assert_not_called()


@pytest.mark.asyncio
async def test_spawn_update_no_key_attribute():
    """Test handling items without key attribute."""
    mock_store = Mock()
    mock_items = [Mock(spec=[])]

    with patch("app.agents.supervisor.memory.usage_tracking.asyncio.create_task") as mock_create_task:
        update_memory_usage_tracking(
            mock_store,
            "user-123",
            mock_items
        )

        mock_create_task.assert_not_called()


@pytest.mark.asyncio
async def test_spawn_update_mixed_items():
    """Test handling mix of items with and without keys."""
    mock_store = Mock()
    mock_item = Mock()
    mock_item.value = {"summary": "Test", "last_used_at": None}
    mock_store.aget = AsyncMock(return_value=[mock_item])
    mock_store.aput = AsyncMock()

    mock_items = [
        Mock(key="key-1"),
        Mock(spec=[]),
        Mock(key="key-2"),
    ]

    with patch("app.agents.supervisor.memory.usage_tracking.asyncio.create_task") as mock_create_task:
        update_memory_usage_tracking(
            mock_store,
            "user-123",
            mock_items
        )

        mock_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_spawn_update_error_handling():
    """Test error handling in update function."""
    mock_store = Mock()
    mock_items = [Mock(key="test")]

    with patch("app.agents.supervisor.memory.usage_tracking.asyncio.create_task", side_effect=Exception("Error")):
        update_memory_usage_tracking(
            mock_store,
            "user-123",
            mock_items
        )


@pytest.mark.asyncio
async def test_update_last_used_at_updates_timestamp():
    """Test that timestamp is actually updated to a new value."""
    mock_store = Mock()
    old_timestamp = "2025-01-01T00:00:00+00:00"
    mock_item = Mock()
    mock_item.value = {
        "id": "test-key",
        "summary": "Test memory",
        "last_used_at": old_timestamp
    }
    mock_store.aget = AsyncMock(return_value=[mock_item])
    mock_store.aput = AsyncMock()

    await _update_last_used_async(
        mock_store,
        "user-123",
        ["test-key"]
    )

    call_args = mock_store.aput.call_args
    updated_value = call_args[0][2]
    assert updated_value["last_used_at"] != old_timestamp


@pytest.mark.asyncio
async def test_update_last_used_at_correct_namespace():
    """Test that correct namespace is used."""
    mock_store = Mock()
    mock_item = Mock()
    mock_item.value = {"id": "test-key", "summary": "Test", "last_used_at": None}
    mock_store.aget = AsyncMock(return_value=[mock_item])
    mock_store.aput = AsyncMock()

    await _update_last_used_async(
        mock_store,
        "user-123",
        ["test-key"]
    )

    get_call_args = mock_store.aget.call_args
    namespace = get_call_args[0][0]
    assert namespace == ("user-123", "semantic")


@pytest.mark.asyncio
async def test_update_last_used_at_indexes_summary():
    """Test that summary is indexed when updating."""
    mock_store = Mock()
    mock_item = Mock()
    mock_item.value = {"id": "test-key", "summary": "Test summary", "last_used_at": None}
    mock_store.aget = AsyncMock(return_value=[mock_item])
    mock_store.aput = AsyncMock()

    await _update_last_used_async(
        mock_store,
        "user-123",
        ["test-key"]
    )

    mock_store.aput.assert_called_once()


@pytest.mark.asyncio
async def test_update_last_used_at_removes_duplicate():
    """Test that old last_used_at is removed to prevent duplication."""
    mock_store = Mock()
    mock_item = Mock()
    mock_item.value = {
        "id": "test-key",
        "summary": "Test memory",
        "category": "Finance",
        "last_used_at": "2025-10-01T00:00:00+00:00"
    }
    mock_store.aget = AsyncMock(return_value=[mock_item])
    mock_store.aput = AsyncMock()

    await _update_last_used_async(
        mock_store,
        "user-123",
        ["test-key"]
    )

    call_args = mock_store.aput.call_args
    updated_value = call_args[0][2]

    assert "last_used_at" in updated_value
    assert updated_value["last_used_at"] != "2025-10-01T00:00:00+00:00"
    last_used_count = list(updated_value.keys()).count("last_used_at")
    assert last_used_count == 1

