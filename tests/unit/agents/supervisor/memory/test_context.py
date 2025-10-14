"""
Unit tests for app.agents.supervisor.memory.context module.

Tests cover:
- User text extraction from messages
- Scoring and ranking functions
- Memory item merging and selection
- Context response building
- Timezone resolution
- Routing examples extraction
- Main memory_context function
"""

from datetime import timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.agents.supervisor.memory.context import (
    _build_context_response,
    _extract_routing_examples,
    _extract_user_text,
    _items_to_bullets,
    _merge_semantic_items,
    _resolve_user_tz_from_config,
    _safe_extract_score,
    _safe_extract_summary,
    _score_factory,
    _select_episodic_items,
    _timed_search,
    memory_context,
)


class TestExtractUserText:
    """Test _extract_user_text function."""

    def test_extract_user_text_with_human_message(self):
        """Test extracting text from HumanMessage."""
        from langchain_core.messages import HumanMessage

        messages = [
            HumanMessage(content="Hello"),
            HumanMessage(content="How are you?"),
        ]

        result = _extract_user_text(messages)
        assert result == "How are you?"

    def test_extract_user_text_with_dict_messages(self):
        """Test extracting text from dict messages."""
        # Create mock objects with role and content attributes
        assistant_msg = MagicMock()
        assistant_msg.role = "assistant"
        assistant_msg.content = "Assistant response"

        user_msg = MagicMock()
        user_msg.role = "user"
        user_msg.content = "User message"

        messages = [assistant_msg, user_msg]

        result = _extract_user_text(messages)
        assert result == "User message"

    def test_extract_user_text_skip_context_profile(self):
        """Test skipping messages that start with CONTEXT_PROFILE."""
        context_msg = MagicMock()
        context_msg.role = "user"
        context_msg.content = "CONTEXT_PROFILE: some profile"

        regular_msg = MagicMock()
        regular_msg.role = "user"
        regular_msg.content = "Regular user message"

        messages = [context_msg, regular_msg]

        result = _extract_user_text(messages)
        assert result == "Regular user message"

    def test_extract_user_text_skip_relevant_context(self):
        """Test skipping messages that start with 'Relevant context for tailoring this turn:'."""
        context_msg = MagicMock()
        context_msg.role = "user"
        context_msg.content = "Relevant context for tailoring this turn: some context"

        actual_msg = MagicMock()
        actual_msg.role = "user"
        actual_msg.content = "Actual user message"

        messages = [context_msg, actual_msg]

        result = _extract_user_text(messages)
        assert result == "Actual user message"

    def test_extract_user_text_no_user_messages(self):
        """Test with no user messages."""
        messages = [
            {"role": "assistant", "content": "Assistant response"},
            {"role": "system", "content": "System message"},
        ]

        result = _extract_user_text(messages)
        assert result is None

    def test_extract_user_text_empty_messages(self):
        """Test with empty message list."""
        result = _extract_user_text([])
        assert result is None


class TestScoreFactory:
    """Test _score_factory function."""

    def test_score_factory_basic_scoring(self):
        """Test basic scoring calculation."""
        weights = {"sim": 0.4, "imp": 0.3, "recency": 0.2, "pinned": 0.1}

        score_fn = _score_factory(weights)

        # Mock item with score, importance, and pinned
        mock_item = MagicMock()
        mock_item.score = 0.8
        mock_item.value = {"importance": 3, "pinned": True}
        mock_item.updated_at = "2024-01-01T00:00:00Z"

        result = score_fn(mock_item)

        # Should be a float between 0 and 1
        assert isinstance(result, float)
        assert 0 <= result <= 1

    def test_score_factory_with_missing_attributes(self):
        """Test scoring with missing attributes."""
        weights = {"sim": 0.4, "imp": 0.3, "recency": 0.2, "pinned": 0.1}

        score_fn = _score_factory(weights)

        mock_item = MagicMock()
        mock_item.score = None
        mock_item.value = {}
        mock_item.updated_at = None

        result = score_fn(mock_item)

        assert isinstance(result, float)
        assert result == 0.0


class TestMergeSemanticItems:
    """Test _merge_semantic_items function."""

    def test_merge_semantic_items_basic_merge(self):
        """Test basic merging of semantic items."""
        mock_items = []
        for i in range(5):
            mock_item = MagicMock()
            mock_item.key = f"key_{i}"
            mock_item.score = 0.8 - i * 0.1  # Decreasing scores
            mock_item.value = {"importance": 3}
            mock_items.append(mock_item)

        def score_fn(item):
            return float(getattr(item, "score", 0.0) or 0.0)

        result = _merge_semantic_items(mock_items, 3, score_fn)

        assert len(result) == 3
        # Should include top raw scores and reranked items
        assert all(item in mock_items for item in result)

    def test_merge_semantic_items_empty_list(self):
        """Test merging with empty list."""
        result = _merge_semantic_items([], 3, lambda x: 0.0)
        assert result == []

    def test_merge_semantic_items_duplicate_keys(self):
        """Test handling of duplicate keys."""
        mock_item1 = MagicMock()
        mock_item1.key = "duplicate"
        mock_item1.score = 0.9

        mock_item2 = MagicMock()
        mock_item2.key = "duplicate"
        mock_item2.score = 0.8

        mock_items = [mock_item1, mock_item2]

        def score_fn(item):
            return float(getattr(item, "score", 0.0) or 0.0)

        result = _merge_semantic_items(mock_items, 2, score_fn)

        # Should only include one item with duplicate key
        assert len(result) == 1
        assert result[0].key == "duplicate"


class TestSelectEpisodicItems:
    """Test _select_episodic_items function."""

    def test_select_episodic_items_basic_selection(self):
        """Test basic selection of episodic items."""
        mock_items = []
        for i in range(5):
            mock_item = MagicMock()
            mock_item.score = 0.8 - i * 0.1
            mock_items.append(mock_item)

        def score_fn(item):
            return float(getattr(item, "score", 0.0) or 0.0)

        result = _select_episodic_items(mock_items, 4, score_fn)

        assert len(result) == 2  # topn // 2 = 4 // 2 = 2
        # Should be sorted by score descending
        assert result[0].score >= result[1].score

    def test_select_episodic_items_empty_list(self):
        """Test selection with empty list."""
        result = _select_episodic_items([], 4, lambda x: 0.0)
        assert result == []


class TestItemsToBullets:
    """Test _items_to_bullets function."""

    def test_items_to_bullets_basic_conversion(self):
        """Test basic conversion to bullets."""
        # Mock episodic item
        epi_item = MagicMock()
        epi_item.value = {"summary": "Previous conversation"}
        epi_item.updated_at = "2024-01-01T00:00:00Z"
        epi_item.created_at = "2024-01-01T00:00:00Z"

        # Mock semantic item
        sem_item = MagicMock()
        sem_item.value = {"summary": "User fact", "category": "Personal"}
        sem_item.updated_at = "2024-01-01T00:00:00Z"
        sem_item.created_at = "2024-01-01T00:00:00Z"

        epi_items = [epi_item]
        sem_items = [sem_item]

        epi_bullets, sem_bullets = _items_to_bullets(epi_items, sem_items, 2, timezone.utc)

        assert len(epi_bullets) == 1
        assert len(sem_bullets) == 1
        assert "Previous conversation" in epi_bullets[0]
        assert "[Personal] User fact" in sem_bullets[0]

    def test_items_to_bullets_empty_items(self):
        """Test with empty item lists."""
        epi_bullets, sem_bullets = _items_to_bullets([], [], 2, timezone.utc)

        assert epi_bullets == []
        assert sem_bullets == []


class TestResolveUserTzFromConfig:
    """Test _resolve_user_tz_from_config function."""

    def test_resolve_user_tz_from_config_with_timezone(self):
        """Test resolving timezone from config."""
        config = MagicMock()
        config.configurable = {
            "user_context": {
                "locale_info": {"time_zone": "America/New_York"}
            }
        }

        result = _resolve_user_tz_from_config(config)

        # Should return a timezone object
        assert hasattr(result, 'utcoffset')

    def test_resolve_user_tz_from_config_default_utc(self):
        """Test defaulting to UTC when no timezone specified."""
        config = MagicMock()
        config.configurable = {}

        result = _resolve_user_tz_from_config(config)

        # Should return a timezone object (either zoneinfo.ZoneInfo or datetime.timezone)
        assert hasattr(result, 'utcoffset')
        # Should be equivalent to UTC
        assert result.utcoffset(None) == timezone.utc.utcoffset(None)

    @patch("builtins.__import__")
    def test_resolve_user_tz_from_config_fallback(self, mock_import):
        """Test fallback when zoneinfo is not available."""
        # Mock the import to raise an exception when importing zoneinfo
        def mock_import_func(name, *args, **kwargs):
            if name == "zoneinfo":
                raise ImportError("zoneinfo not available")
            return __import__(name, *args, **kwargs)

        mock_import.side_effect = mock_import_func

        config = MagicMock()
        config.configurable = {
            "user_context": {
                "locale_info": {"time_zone": "America/New_York"}
            }
        }

        result = _resolve_user_tz_from_config(config)

        assert result == timezone.utc


class TestTimedSearch:
    """Test _timed_search function."""

    @pytest.mark.asyncio
    async def test_timed_search_basic_search(self):
        """Test basic timed search."""
        mock_store = MagicMock()
        mock_results = [MagicMock(), MagicMock()]
        mock_store.search.return_value = mock_results

        result = await _timed_search(
            mock_store, ("user", "semantic"), query="test query", limit=5, label="test"
        )

        assert result == mock_results
        mock_store.search.assert_called_once_with(("user", "semantic"), query="test query", filter=None, limit=5)


class TestExtractRoutingExamples:
    """Test _extract_routing_examples function."""

    def test_extract_routing_examples_basic_extraction(self):
        """Test basic extraction of routing examples."""
        mock_items = []
        for i in range(3):
            mock_item = MagicMock()
            mock_item.score = 0.8
            mock_item.value = {"summary": f"Routing example {i}"}
            mock_items.append(mock_item)

        result = _extract_routing_examples(mock_items)

        assert len(result) == 3
        assert all("Example:" in example for example in result)

    def test_extract_routing_examples_with_low_score(self):
        """Test filtering out low score items."""
        mock_item = MagicMock()
        mock_item.score = 0.1  # Below PROCEDURAL_MIN_SCORE
        mock_item.value = {"summary": "Low score example"}

        result = _extract_routing_examples([mock_item])

        assert result == []

    def test_extract_routing_examples_empty_list(self):
        """Test with empty list."""
        result = _extract_routing_examples([])
        assert result == []

    def test_extract_routing_examples_long_summary(self):
        """Test truncation of long summaries."""
        long_summary = "A" * 250
        mock_item = MagicMock()
        mock_item.score = 0.8
        mock_item.value = {"summary": long_summary}

        result = _extract_routing_examples([mock_item])

        assert len(result) == 1
        assert "..." in result[0]
        assert len(result[0]) <= 250  # Should be truncated


class TestSafeExtractScore:
    """Test _safe_extract_score function."""

    def test_safe_extract_score_valid_score(self):
        """Test extracting valid score."""
        mock_item = MagicMock()
        mock_item.score = 0.85

        result = _safe_extract_score(mock_item)

        assert result == 0.85

    def test_safe_extract_score_none_score(self):
        """Test handling None score."""
        mock_item = MagicMock()
        mock_item.score = None

        result = _safe_extract_score(mock_item)

        assert result == 0.0

    def test_safe_extract_score_invalid_score(self):
        """Test handling invalid score type."""
        mock_item = MagicMock()
        mock_item.score = "invalid"

        result = _safe_extract_score(mock_item)

        assert result == 0.0


class TestSafeExtractSummary:
    """Test _safe_extract_summary function."""

    def test_safe_extract_summary_valid_summary(self):
        """Test extracting valid summary."""
        mock_item = MagicMock()
        mock_item.value = {"summary": "Test summary"}

        result = _safe_extract_summary(mock_item)

        assert result == "Test summary"

    def test_safe_extract_summary_missing_value(self):
        """Test handling missing value."""
        mock_item = MagicMock()
        mock_item.value = None

        result = _safe_extract_summary(mock_item)

        assert result == ""

    def test_safe_extract_summary_missing_summary(self):
        """Test handling missing summary."""
        mock_item = MagicMock()
        mock_item.value = {}

        result = _safe_extract_summary(mock_item)

        assert result == ""


class TestBuildContextResponse:
    """Test _build_context_response function."""

    def test_build_context_response_basic_response(self):
        """Test basic context response building."""
        epi_bullets = ["Episodic memory 1", "Episodic memory 2"]
        sem_bullets = ["[Personal] User fact 1", "[Finance] User fact 2"]
        routing_examples = ["Example: routing guidance"]

        config = MagicMock()
        config.configurable = {}

        result = _build_context_response(epi_bullets, sem_bullets, config, routing_examples)

        assert "messages" in result
        assert len(result["messages"]) == 1
        content = result["messages"][0].content

        assert "CURRENT TIME:" in content
        assert "EPISODIC MEMORIES" in content
        assert "SEMANTIC MEMORIES" in content
        assert "ROUTING GUIDANCE" in content

    def test_build_context_response_minimal_response(self):
        """Test response with minimal data."""
        config = MagicMock()
        config.configurable = {}

        result = _build_context_response([], [], config)

        assert "messages" in result
        content = result["messages"][0].content
        assert "CURRENT TIME:" in content
        assert "EPISODIC MEMORIES" not in content
        assert "SEMANTIC MEMORIES" not in content


class TestMemoryContext:
    """Test memory_context function."""

    @pytest.mark.asyncio
    async def test_memory_context_successful_retrieval(self):
        """Test successful memory context retrieval."""
        from langchain_core.messages import HumanMessage

        state = {"messages": [HumanMessage(content="Hello")]}

        config = MagicMock()
        config.configurable = {
            "user_id": str(uuid4()),
            "user_context": {"locale_info": {"time_zone": "UTC"}}
        }

        # Mock search results with proper structure
        mock_sem_item = MagicMock()
        mock_sem_item.key = "sem_key"
        mock_sem_item.score = 0.8
        mock_sem_item.value = {"summary": "User fact", "category": "Personal", "importance": 3}
        mock_sem_item.updated_at = "2024-01-01T00:00:00Z"

        mock_store = MagicMock()
        mock_store.search = MagicMock(side_effect=[
            [mock_sem_item],  # semantic results
            [],  # episodic results (empty)
            []   # procedural results (empty)
        ])

        with patch("app.agents.supervisor.memory.context.get_store", return_value=mock_store), \
             patch("app.agents.supervisor.memory.context._parse_weights", return_value={"sim": 0.4, "imp": 0.3, "recency": 0.2, "pinned": 0.1}), \
             patch("app.agents.supervisor.memory.context.CONTEXT_TOPN", 2), \
             patch("app.agents.supervisor.memory.context.CONTEXT_TOPK", 5), \
             patch("app.agents.supervisor.memory.context.PROCEDURAL_TOPK", 3), \
             patch("app.agents.supervisor.memory.context.PROCEDURAL_MIN_SCORE", 0.5), \
             patch("app.agents.supervisor.memory.context.RERANK_WEIGHTS_RAW", "sim:0.4,imp:0.3,recency:0.2,pinned:0.1"):

            result = await memory_context(state, config)

            assert "messages" in result
            assert len(result["messages"]) == 1
            content = result["messages"][0].content
            assert "Relevant context for tailoring this turn:" in content
            assert "SEMANTIC MEMORIES" in content

    @pytest.mark.asyncio
    async def test_memory_context_no_user_id(self):
        """Test memory context with no user ID."""
        state = {"messages": []}

        config = MagicMock()
        config.configurable = {}

        result = await memory_context(state, config)

        assert result == {}

    @pytest.mark.asyncio
    async def test_memory_context_no_memories_found(self):
        """Test memory context when no memories are found."""
        from langchain_core.messages import HumanMessage

        state = {"messages": [HumanMessage(content="Hello")]}

        config = MagicMock()
        config.configurable = {"user_id": str(uuid4())}

        with patch("app.agents.supervisor.memory.context.get_store") as mock_get_store, \
             patch("app.agents.supervisor.memory.context._parse_weights") as mock_parse_weights:

            mock_store = MagicMock()
            mock_get_store.return_value = mock_store

            # Mock empty search results
            mock_store.search = AsyncMock(return_value=[])

            mock_parse_weights.return_value = {"sim": 0.4, "imp": 0.3, "recency": 0.2, "pinned": 0.1}

            result = await memory_context(state, config)

            assert result == {}

