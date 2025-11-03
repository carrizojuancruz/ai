from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.agents.supervisor.memory_tools import (
    _normalize_category,
    _utc_now_iso,
    episodic_memory_fetch,
    episodic_memory_put,
    episodic_memory_update,
    semantic_memory_put,
    semantic_memory_search,
    semantic_memory_update,
)


@pytest.mark.unit
class TestNormalizeCategory:

    @pytest.mark.parametrize(
        "input_val,expected",
        [
            ("Finance", "Finance"),
            ("finance", "Finance"),
            ("FINANCE", "Finance"),
            ("Budget", "Budget"),
            ("Goals", "Goals"),
            ("Personal", "Personal"),
            ("Education", "Education"),
            ("Conversation_Summary", "Conversation_Summary"),
            ("conversation_summary", "Conversation_Summary"),
            ("conversation summary", "Conversation_Summary"),
            ("FiNaNcE", "Finance"),
            ("BUDGET", "Budget"),
            ("Other", "Other"),
            ("InvalidCategory", "Other"),
            ("Random", "Other"),
            ("", "Other"),
            ("   ", "Other"),
            (None, "Other"),
        ],
    )
    def test_normalize_category(self, input_val, expected):
        """Parametrized test covering all category normalization scenarios."""
        assert _normalize_category(input_val) == expected


@pytest.mark.unit
class TestUtcNowIso:
    """Test suite for _utc_now_iso function."""

    def test_returns_string(self):
        """Test that function returns a string."""
        result = _utc_now_iso()
        assert isinstance(result, str)

    def test_returns_iso_format(self):
        """Test that function returns ISO 8601 format."""
        result = _utc_now_iso()
        parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
        assert isinstance(parsed, datetime)

    def test_returns_utc_timezone(self):
        """Test that returned datetime is in UTC."""
        result = _utc_now_iso()
        parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
        assert parsed.tzinfo is not None

    def test_timestamp_is_recent(self):
        """Test that timestamp is recent (within last second)."""
        before = datetime.now(timezone.utc)
        result = _utc_now_iso()
        after = datetime.now(timezone.utc)

        parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
        assert before <= parsed <= after


@pytest.mark.unit
class TestSemanticMemorySearch:
    """Test suite for semantic_memory_search function."""

    @pytest.mark.asyncio
    async def test_search_with_query(self, mock_langgraph_store, mock_config):
        """Test semantic search with a query."""
        result = await semantic_memory_search(
            query="communication preferences",
            config=mock_config,
        )

        assert isinstance(result, list)
        assert len(result) > 0
        mock_langgraph_store.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_with_topic_filter(self, mock_langgraph_store, mock_config):
        """Test search with topic filter."""
        result = await semantic_memory_search(
            topic="Personal",
            query="preferences",
            config=mock_config,
        )

        assert isinstance(result, list)
        call_args = mock_langgraph_store.search.call_args
        assert call_args[1]["filter"] is not None

    @pytest.mark.asyncio
    async def test_search_with_limit(self, mock_langgraph_store, mock_config):
        """Test search with custom limit."""
        limit = 10
        await semantic_memory_search(
            query="test",
            limit=limit,
            config=mock_config,
        )

        call_args = mock_langgraph_store.search.call_args
        assert call_args[1]["limit"] == limit

    @pytest.mark.asyncio
    async def test_search_normalizes_category(self, mock_langgraph_store, mock_config):
        """Test that search normalizes the topic category."""
        await semantic_memory_search(
            topic="finance",
            query="test",
            config=mock_config,
        )

        call_args = mock_langgraph_store.search.call_args
        filter_param = call_args[1]["filter"]
        assert filter_param["category"] == "Finance"

    @pytest.mark.asyncio
    async def test_search_fallback_without_filter(self, mock_langgraph_store, mock_config):
        """Test search fallback when category filter returns no results."""
        mock_langgraph_store.search.side_effect = [[], [MagicMock(value={"id": "test"})]]

        result = await semantic_memory_search(
            topic="Personal",
            query="test",
            config=mock_config,
        )

        assert mock_langgraph_store.search.call_count == 2
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_without_query_returns_empty(self, mock_langgraph_store, mock_config):
        """Test that search without query returns empty list."""
        result = await semantic_memory_search(
            query=None,
            config=mock_config,
        )

        assert result == []
        mock_langgraph_store.search.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_missing_user_id_returns_empty(self, mock_langgraph_store, mock_config_no_user):
        """Test that search without user_id returns empty list."""
        result = await semantic_memory_search(
            query="test",
            config=mock_config_no_user,
        )

        assert result == []
        mock_langgraph_store.search.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_returns_item_values(self, mock_langgraph_store, mock_config):
        """Test that search returns the value attribute of items."""
        result = await semantic_memory_search(
            query="test",
            config=mock_config,
        )

        assert all(isinstance(item, dict) for item in result)


@pytest.mark.unit
class TestEpisodicMemoryFetch:
    """Test suite for episodic_memory_fetch function."""

    @pytest.mark.asyncio
    async def test_fetch_with_query(self, mock_langgraph_store, mock_config):
        """Test episodic fetch with query."""
        result = await episodic_memory_fetch(
            query="recent conversation",
            config=mock_config,
        )

        assert isinstance(result, list)
        mock_langgraph_store.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_without_query_uses_default(self, mock_langgraph_store, mock_config):
        """Test that fetch without query uses default query."""
        await episodic_memory_fetch(
            query=None,
            config=mock_config,
        )

        call_args = mock_langgraph_store.search.call_args
        assert "recent conversation" in call_args[0] or call_args[1]["query"] == "recent conversation"

    @pytest.mark.asyncio
    async def test_fetch_with_topic_filter(self, mock_langgraph_store, mock_config):
        """Test fetch with topic filter."""
        await episodic_memory_fetch(
            topic="Conversation_Summary",
            query="test",
            config=mock_config,
        )

        call_args = mock_langgraph_store.search.call_args
        assert call_args[1]["filter"] is not None

    @pytest.mark.asyncio
    async def test_fetch_missing_user_id_returns_empty(self, mock_langgraph_store, mock_config_no_user):
        """Test that fetch without user_id returns empty list."""
        result = await episodic_memory_fetch(
            query="test",
            config=mock_config_no_user,
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_with_custom_limit(self, mock_langgraph_store, mock_config):
        """Test fetch with custom limit."""
        limit = 5
        await episodic_memory_fetch(
            query="test",
            limit=limit,
            config=mock_config,
        )

        call_args = mock_langgraph_store.search.call_args
        assert call_args[1]["limit"] == limit


@pytest.mark.unit
class TestSemanticMemoryPut:
    """Test suite for semantic_memory_put function."""

    @pytest.mark.asyncio
    async def test_put_basic_memory(self, mock_memory_service, mock_config):
        """Test putting a basic semantic memory."""
        result = await semantic_memory_put(
            summary="User prefers email communication",
            config=mock_config,
        )

        assert result["ok"] is True
        assert "key" in result
        assert "value" in result
        mock_memory_service.create_memory.assert_called_once()

    @pytest.mark.asyncio
    async def test_put_with_all_fields(self, mock_memory_service, mock_config):
        """Test putting memory with all fields."""
        result = await semantic_memory_put(
            summary="User has a cat named Fluffy",
            category="Personal",
            key="custom_key",
            tags=["pets", "personal"],
            source="chat",
            importance=5,
            pinned=True,
            config=mock_config,
        )

        assert result["ok"] is True
        value = result["value"]
        assert value["summary"] == "User has a cat named Fluffy"
        assert value["category"] == "Personal"
        assert value["tags"] == ["pets", "personal"]
        assert value["importance"] == 5
        assert value["pinned"] is True

    @pytest.mark.asyncio
    async def test_put_generates_key_if_missing(self, mock_memory_service, mock_config):
        """Test that put generates key if not provided."""
        result = await semantic_memory_put(
            summary="Test memory",
            config=mock_config,
        )

        assert result["ok"] is True
        assert len(result["key"]) > 0

    @pytest.mark.asyncio
    async def test_put_normalizes_category(self, mock_memory_service, mock_config):
        """Test that put normalizes category."""
        result = await semantic_memory_put(
            summary="Test",
            category="finance",
            config=mock_config,
        )

        assert result["value"]["category"] == "Finance"

    @pytest.mark.asyncio
    async def test_put_sets_timestamps(self, mock_memory_service, mock_config):
        """Test that put sets created_at and last_accessed timestamps."""
        result = await semantic_memory_put(
            summary="Test",
            config=mock_config,
        )

        value = result["value"]
        assert "created_at" in value
        assert "last_accessed" in value
        datetime.fromisoformat(value["created_at"].replace("Z", "+00:00"))

    @pytest.mark.asyncio
    async def test_put_sets_default_values(self, mock_memory_service, mock_config):
        """Test that put sets appropriate default values."""
        result = await semantic_memory_put(
            summary="Test",
            config=mock_config,
        )

        value = result["value"]
        assert value["type"] == "semantic"
        assert value["tags"] == []
        assert value["source"] == "chat"
        assert value["importance"] == 1
        assert value["pinned"] is False

    @pytest.mark.asyncio
    async def test_put_missing_user_id_returns_error(self, mock_memory_service, mock_config_no_user):
        """Test that put without user_id returns error."""
        result = await semantic_memory_put(
            summary="Test",
            config=mock_config_no_user,
        )

        assert result["ok"] is False
        assert "error" in result
        assert result["error"] == "missing_user_id"

    @pytest.mark.asyncio
    async def test_put_indexes_summary_field(self, mock_memory_service, mock_config):
        """Test that put indexes the summary field."""
        await semantic_memory_put(
            summary="Test memory",
            config=mock_config,
        )

        call_args = mock_memory_service.create_memory.call_args
        assert call_args[1]["index"] == ["summary"]


@pytest.mark.unit
class TestEpisodicMemoryPut:
    """Test suite for episodic_memory_put function."""

    @pytest.mark.asyncio
    async def test_put_basic_episodic_memory(self, mock_memory_service, mock_config):
        """Test putting a basic episodic memory."""
        result = await episodic_memory_put(
            summary="User discussed budgeting strategies",
            config=mock_config,
        )

        assert result["ok"] is True
        assert "key" in result
        assert result["value"]["type"] == "episodic"

    @pytest.mark.asyncio
    async def test_put_stores_in_episodic_namespace(self, mock_memory_service, mock_config):
        """Test that episodic memories are stored in correct namespace."""
        await episodic_memory_put(
            summary="Test",
            config=mock_config,
        )

        mock_memory_service.create_memory.assert_called_once()
        call_args = mock_memory_service.create_memory.call_args
        if len(call_args.args) > 1:
            assert call_args.args[1] == "episodic"
        else:
            assert call_args.kwargs.get("memory_type") == "episodic"

    @pytest.mark.asyncio
    async def test_put_with_all_episodic_fields(self, mock_memory_service, mock_config):
        """Test putting episodic memory with all fields."""
        result = await episodic_memory_put(
            summary="Conversation about goals",
            category="Conversation_Summary",
            key="episode_1",
            tags=["goals", "planning"],
            importance=4,
            config=mock_config,
        )

        value = result["value"]
        assert value["category"] == "Conversation_Summary"
        assert value["importance"] == 4


@pytest.mark.unit
class TestSemanticMemoryUpdate:
    """Test suite for semantic_memory_update function."""

    @pytest.mark.asyncio
    async def test_update_existing_memory(self, mock_langgraph_store, mock_config):
        """Test updating an existing semantic memory."""
        result = await semantic_memory_update(
            key="test_memory_123",
            summary="Updated summary",
            config=mock_config,
        )

        assert result["ok"] is True
        assert result["value"]["summary"] == "Updated summary"

    @pytest.mark.asyncio
    async def test_update_partial_fields(self, mock_langgraph_store, mock_config):
        """Test updating only specific fields."""
        result = await semantic_memory_update(
            key="test_memory_123",
            importance=5,
            pinned=True,
            config=mock_config,
        )

        assert result["ok"] is True
        value = result["value"]
        assert value["importance"] == 5
        assert value["pinned"] is True

    @pytest.mark.asyncio
    async def test_update_nonexistent_memory_returns_error(self, mock_langgraph_store, mock_config):
        """Test updating non-existent memory returns error."""
        mock_langgraph_store.get.return_value = None

        result = await semantic_memory_update(
            key="nonexistent",
            summary="Test",
            config=mock_config,
        )

        assert result["ok"] is False
        assert result["error"] == "not_found"

    @pytest.mark.asyncio
    async def test_update_updates_last_accessed(self, mock_langgraph_store, mock_config):
        """Test that update updates last_accessed timestamp."""
        result = await semantic_memory_update(
            key="test_memory_123",
            summary="Updated",
            config=mock_config,
        )

        value = result["value"]
        assert "last_accessed" in value
        parsed = datetime.fromisoformat(value["last_accessed"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        assert (now - parsed).total_seconds() < 2

    @pytest.mark.asyncio
    async def test_update_none_fields_are_ignored(self, mock_langgraph_store, mock_config):
        """Test that None fields are not updated."""
        original_importance = mock_langgraph_store.get.return_value.value.get("importance", 3)

        result = await semantic_memory_update(
            key="test_memory_123",
            summary="New summary",
            importance=None,
            config=mock_config,
        )

        assert result["value"]["importance"] == original_importance

    @pytest.mark.asyncio
    async def test_update_missing_user_id_returns_error(self, mock_langgraph_store, mock_config_no_user):
        """Test that update without user_id returns error."""
        result = await semantic_memory_update(
            key="test",
            summary="Test",
            config=mock_config_no_user,
        )

        assert result["ok"] is False
        assert result["error"] == "missing_user_id"


@pytest.mark.unit
class TestEpisodicMemoryUpdate:
    """Test suite for episodic_memory_update function."""

    @pytest.mark.asyncio
    async def test_update_existing_episodic_memory(self, mock_langgraph_store, mock_config):
        """Test updating an existing episodic memory."""
        mock_item = MagicMock()
        mock_item.value = {
            "id": "episode_1",
            "type": "episodic",
            "summary": "Original summary",
            "category": "Other",
            "importance": 2,
        }
        mock_langgraph_store.get.return_value = mock_item

        result = await episodic_memory_update(
            key="episode_1",
            summary="Updated episodic summary",
            config=mock_config,
        )

        assert result["ok"] is True
        assert result["value"]["summary"] == "Updated episodic summary"

    @pytest.mark.asyncio
    async def test_update_episodic_category(self, mock_langgraph_store, mock_config):
        """Test updating episodic memory category."""
        mock_item = MagicMock()
        mock_item.value = {
            "id": "episode_1",
            "type": "episodic",
            "summary": "Test",
            "category": "Other",
        }
        mock_langgraph_store.get.return_value = mock_item

        result = await episodic_memory_update(
            key="episode_1",
            category="Conversation_Summary",
            config=mock_config,
        )

        assert result["value"]["category"] == "Conversation_Summary"

    @pytest.mark.asyncio
    async def test_update_episodic_nonexistent_returns_error(self, mock_langgraph_store, mock_config):
        """Test updating non-existent episodic memory."""
        mock_langgraph_store.get.return_value = None

        result = await episodic_memory_update(
            key="nonexistent",
            summary="Test",
            config=mock_config,
        )

        assert result["ok"] is False
        assert result["error"] == "not_found"
