"""Tests for helper functions in wealth agent subgraph."""

from unittest.mock import MagicMock

import pytest

from app.agents.supervisor.wealth_agent.subgraph import (
    extract_text_content_from_message,
    filter_sources_by_urls,
    select_primary_subcategory,
)


@pytest.mark.unit
class TestFilterSourcesByUrls:
    """Test suite for filter_sources_by_urls function."""

    def test_filter_sources_matches_urls(self):
        """Test filtering sources by matching URLs."""
        sources = [
            {"url": "http://example.com/1", "name": "Doc1"},
            {"url": "http://example.com/2", "name": "Doc2"},
            {"url": "http://example.com/3", "name": "Doc3"},
        ]
        urls = ["http://example.com/1", "http://example.com/3"]

        result = filter_sources_by_urls(sources, urls)

        assert len(result) == 2
        assert result[0]["url"] == "http://example.com/1"
        assert result[1]["url"] == "http://example.com/3"

    def test_filter_sources_non_matching_urls(self):
        """Test filtering returns empty when no URLs match."""
        sources = [
            {"url": "http://example.com/1", "name": "Doc1"},
            {"url": "http://example.com/2", "name": "Doc2"},
        ]
        urls = ["http://different.com/1"]

        result = filter_sources_by_urls(sources, urls)

        assert len(result) == 0

    def test_filter_sources_removes_duplicates(self):
        """Test duplicate URLs are removed (first occurrence kept)."""
        sources = [
            {"url": "http://example.com/1", "name": "Doc1"},
            {"url": "http://example.com/1", "name": "Doc1 Duplicate"},
            {"url": "http://example.com/2", "name": "Doc2"},
        ]
        urls = ["http://example.com/1", "http://example.com/2"]

        result = filter_sources_by_urls(sources, urls)

        assert len(result) == 2
        assert result[0]["name"] == "Doc1"
        assert result[1]["name"] == "Doc2"

    def test_filter_sources_includes_internal_sources(self):
        """Test internal sources are included (not filtered out)."""
        sources = [
            {"url": "http://internal.com/1", "name": "Internal", "content_source": "internal", "subcategory": "reports"},
            {"url": "http://external.com/1", "name": "External", "content_source": "external"},
        ]
        urls = ["http://internal.com/1", "http://external.com/1"]

        result = filter_sources_by_urls(sources, urls)

        assert len(result) == 2
        assert any(s.get("content_source") == "internal" for s in result)

    def test_filter_sources_empty_sources_list(self):
        """Test handling of empty sources list."""
        result = filter_sources_by_urls([], ["http://example.com"])

        assert result == []

    def test_filter_sources_empty_urls_list(self):
        """Test handling of empty URLs list."""
        sources = [{"url": "http://example.com", "name": "Doc"}]
        result = filter_sources_by_urls(sources, [])

        assert result == []

    def test_filter_sources_none_url_in_source(self):
        """Test sources without URL field are skipped."""
        sources = [
            {"name": "No URL"},
            {"url": "http://example.com", "name": "Has URL"},
        ]
        urls = ["http://example.com"]

        result = filter_sources_by_urls(sources, urls)

        assert len(result) == 1
        assert result[0]["name"] == "Has URL"


@pytest.mark.unit
class TestExtractTextContentFromMessage:
    """Minimal tests for extract_text_content_from_message."""

    def test_string_content_is_stripped(self):
        msg = MagicMock()
        msg.content = "  some text  "
        assert extract_text_content_from_message(msg) == "some text"

    def test_list_text_blocks_are_joined(self):
        msg = MagicMock()
        msg.content = [
            {"type": "text", "text": "first"},
            {"type": "text", "text": "second"},
        ]
        assert extract_text_content_from_message(msg) == "first\n\nsecond"

    def test_mixed_blocks_ignore_non_text(self):
        msg = MagicMock()
        msg.content = [
            {"type": "image", "data": "..."},
            {"type": "text", "text": "only"},
            {"type": "other"},
        ]
        assert extract_text_content_from_message(msg) == "only"

    def test_empty_list_returns_empty(self):
        msg = MagicMock()
        msg.content = []
        assert extract_text_content_from_message(msg) == ""

    def test_none_content_returns_empty(self):
        msg = MagicMock()
        msg.content = None
        assert extract_text_content_from_message(msg) == ""


@pytest.mark.unit
class TestSelectPrimarySubcategory:
    """Test suite for select_primary_subcategory function."""

    def test_select_empty_list_returns_none(self):
        """Test returns None for empty list."""
        result = select_primary_subcategory([])
        assert result is None

    def test_select_single_item(self):
        """Test returns the single item."""
        result = select_primary_subcategory(["reports"])
        assert result == "reports"

    def test_select_clear_winner_by_frequency(self):
        """Test selects subcategory with highest frequency."""
        subcategories = ["reports", "profile", "reports", "reports", "profile"]
        result = select_primary_subcategory(subcategories)
        assert result == "reports"  # appears 3 times vs profile's 2

    def test_select_tie_resolved_by_first_occurrence(self):
        """Test tie-breaking: selects first occurrence when counts are equal."""
        subcategories = ["profile", "reports", "profile", "reports"]
        result = select_primary_subcategory(subcategories)
        assert result == "profile"  # both appear 2 times, profile comes first

    def test_select_three_way_tie_first_wins(self):
        """Test three-way tie resolved by first occurrence."""
        subcategories = ["connect-account", "reports", "profile", "connect-account", "reports", "profile"]
        result = select_primary_subcategory(subcategories)
        assert result == "connect-account"  # all appear twice, connect-account is first

    def test_select_all_different_returns_first(self):
        """Test when all items appear once, returns first."""
        subcategories = ["reports", "profile", "connect-account"]
        result = select_primary_subcategory(subcategories)
        assert result == "reports"

    def test_select_multiple_of_same_item(self):
        """Test all same item returns that item."""
        subcategories = ["reports", "reports", "reports"]
        result = select_primary_subcategory(subcategories)
        assert result == "reports"

    def test_select_complex_frequency_distribution(self):
        """Test complex distribution: clear winner with multiple other items."""
        subcategories = [
            "reports", "profile", "connect-account",
            "reports", "profile", "reports",
            "connect-account", "reports"
        ]
        result = select_primary_subcategory(subcategories)
        assert result == "reports"  # appears 4 times

    def test_select_tie_with_later_occurrence(self):
        """Test tie where first occurrence is not first in list."""
        subcategories = ["connect-account", "reports", "connect-account", "profile", "reports"]
        result = select_primary_subcategory(subcategories)
        # connect-account: 2, reports: 2, profile: 1
        # Tie between connect-account and reports, connect-account appears first
        assert result == "connect-account"

    def test_select_two_items_equal_counts(self):
        """Test two items with equal counts."""
        subcategories = ["profile", "reports", "profile", "reports", "profile", "reports"]
        result = select_primary_subcategory(subcategories)
        assert result == "profile"  # both equal, profile is first

    def test_select_preserves_original_order_for_ties(self):
        """Test tie-breaking uses original list order, not alphabetical."""
        # If it were alphabetical, "connect-account" < "reports"
        # But we want first occurrence from original list
        subcategories = ["reports", "connect-account", "reports", "connect-account"]
        result = select_primary_subcategory(subcategories)
        assert result == "reports"  # first in original list

    def test_select_single_winner_among_many(self):
        """Test clear single winner with many items."""
        subcategories = [
            "profile", "connect-account", "reports",
            "profile", "connect-account", "profile"
        ]
        result = select_primary_subcategory(subcategories)
        assert result == "profile"  # appears 3 times vs 2 each for others
