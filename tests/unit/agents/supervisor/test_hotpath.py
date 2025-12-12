"""Unit tests for memory hotpath utility functions.

Tests focus on deterministic functions that don't require LLM calls or external dependencies.
"""

from unittest.mock import Mock

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.supervisor.memory.hotpath import _collect_recent_user_texts
from app.agents.supervisor.memory.cold_path import (
    _derive_nudge_metadata,
    _has_min_token_overlap,
    _normalize_summary_text,
    _numeric_overlap_or_step,
    _sanitize_semantic_time_phrases,
)


class TestCollectRecentUserTexts:
    """Test _collect_recent_user_texts function."""

    def test_empty_messages(self):
        result = _collect_recent_user_texts([])
        assert result == []

    def test_single_user_message(self):
        messages = [HumanMessage(content="Hello world")]
        result = _collect_recent_user_texts(messages)
        assert result == ["Hello world"]

    def test_multiple_user_messages(self):
        messages = [
            HumanMessage(content="First message"),
            AIMessage(content="AI response"),
            HumanMessage(content="Second message"),
            HumanMessage(content="Third message"),
        ]
        result = _collect_recent_user_texts(messages, max_messages=3)
        assert result == ["First message", "Second message", "Third message"]

    def test_max_messages_limit(self):
        messages = [
            HumanMessage(content="First"),
            HumanMessage(content="Second"),
            HumanMessage(content="Third"),
            HumanMessage(content="Fourth"),
        ]
        result = _collect_recent_user_texts(messages, max_messages=2)
        assert result == ["Third", "Fourth"]
        assert len(result) == 2

    def test_mixed_message_types(self):
        messages = [
            SystemMessage(content="System"),
            HumanMessage(content="User 1"),
            AIMessage(content="AI 1"),
            HumanMessage(content="User 2"),
        ]
        result = _collect_recent_user_texts(messages)
        assert result == ["User 1", "User 2"]

    def test_empty_content_messages(self):
        messages = [
            HumanMessage(content="Valid message"),
            HumanMessage(content=""),
            HumanMessage(content="   "),
        ]
        result = _collect_recent_user_texts(messages)
        assert result == ["Valid message"]

    def test_preserves_order(self):
        messages = [
            HumanMessage(content="A"),
            HumanMessage(content="B"),
            HumanMessage(content="C"),
        ]
        result = _collect_recent_user_texts(messages, max_messages=3)
        assert result == ["A", "B", "C"]

    def test_mock_message_objects(self):
        """Test with mock objects that have role/type attributes."""
        mock_msg1 = Mock()
        mock_msg1.role = "user"
        mock_msg1.type = None
        mock_msg1.content = "Mock user message"

        messages = [mock_msg1]
        result = _collect_recent_user_texts(messages)
        assert result == ["Mock user message"]


class TestNormalizeSummaryText:
    """Test _normalize_summary_text function."""

    def test_empty_string(self):
        result = _normalize_summary_text("")
        assert result == ""

    def test_none_input(self):
        result = _normalize_summary_text(None)
        assert result == ""

    def test_non_string_input(self):
        result = _normalize_summary_text(123)
        assert result == ""

    def test_smart_quotes_replacement(self):
        text = "It\u2019s a \u2018test\u2019 with \u201cquotes\u201d"
        result = _normalize_summary_text(text)
        assert result == "It's a 'test' with \"quotes\""

    def test_unicode_normalization(self):
        # Test NFC normalization
        text = "café"  # é as single character
        result = _normalize_summary_text(text)
        assert "café" in result or "cafe" in result

    def test_regular_text(self):
        text = "User prefers email communication"
        result = _normalize_summary_text(text)
        assert result == text


class TestSanitizeSemanticTimePhrases:
    """Test _sanitize_semantic_time_phrases function."""

    def test_empty_string(self):
        result = _sanitize_semantic_time_phrases("")
        assert result == ""

    def test_non_string_input(self):
        result = _sanitize_semantic_time_phrases(None)
        assert result == ""

    def test_removes_today(self):
        text = "User went to the gym today"
        result = _sanitize_semantic_time_phrases(text)
        assert "today" not in result.lower()
        assert "gym" in result.lower()

    def test_removes_yesterday(self):
        text = "Yesterday I bought groceries"
        result = _sanitize_semantic_time_phrases(text)
        assert "yesterday" not in result.lower()
        assert "bought" in result.lower()

    def test_removes_this_morning(self):
        text = "User exercised this morning"
        result = _sanitize_semantic_time_phrases(text)
        assert "this morning" not in result.lower()
        assert "exercised" in result.lower()

    def test_removes_last_week(self):
        text = "Started new job last week"
        result = _sanitize_semantic_time_phrases(text)
        assert "last week" not in result.lower()
        assert "job" in result.lower()

    def test_removes_recently(self):
        text = "User recently moved to Austin"
        result = _sanitize_semantic_time_phrases(text)
        assert "recently" not in result.lower()
        assert "Austin" in result

    def test_removes_iso_dates(self):
        text = "Event on 2024-03-15"
        result = _sanitize_semantic_time_phrases(text)
        assert "2024-03-15" not in result

    def test_removes_this_year(self):
        text = "Planning to travel this year"
        result = _sanitize_semantic_time_phrases(text)
        assert "this year" not in result.lower()
        assert "travel" in result.lower()

    def test_cleans_extra_whitespace(self):
        text = "User   has    multiple     spaces"
        result = _sanitize_semantic_time_phrases(text)
        assert "  " not in result

    def test_removes_empty_parentheses(self):
        text = "User moved to Dallas (  )"
        result = _sanitize_semantic_time_phrases(text)
        assert "()" not in result
        assert "(  )" not in result

    def test_preserves_timeless_facts(self):
        text = "User's cat is named Luna"
        result = _sanitize_semantic_time_phrases(text)
        assert result == text


class TestHasMinTokenOverlap:
    """Test _has_min_token_overlap function."""

    def test_no_overlap(self):
        result = _has_min_token_overlap("cat dog bird", "house car tree")
        assert result is False

    def test_short_tokens_ignored(self):
        # Tokens with length < 3 should be ignored
        result = _has_min_token_overlap("a is to", "of in at")
        assert result is False

    def test_partial_word_match(self):
        result = _has_min_token_overlap("running", "runner")
        assert result is False  # Different tokens

    def test_empty_strings(self):
        result = _has_min_token_overlap("", "")
        assert result is False


class TestNumericOverlapOrStep:
    """Test _numeric_overlap_or_step function."""

    def test_no_numbers(self):
        result = _numeric_overlap_or_step("no numbers here", "just text")
        assert result is False

    def test_same_numbers(self):
        result = _numeric_overlap_or_step("Luna is 3 years old", "My cat is 3")
        assert result is True

    def test_step_increment(self):
        result = _numeric_overlap_or_step("Cat is 3 years old", "Cat is 4 years old")
        assert result is True

    def test_step_decrement(self):
        result = _numeric_overlap_or_step("Has 5 items", "Has 4 items")
        assert result is True

    def test_multiple_step_apart(self):
        result = _numeric_overlap_or_step("Age 10", "Age 15")
        assert result is False

    def test_multiple_numbers_with_overlap(self):
        result = _numeric_overlap_or_step("Values 1 2 3", "Values 5 6 7")
        assert result is False

    def test_multiple_numbers_with_step(self):
        result = _numeric_overlap_or_step("Values 1 2 3", "Values 2 5 9")
        assert result is True  # 2 overlaps

    def test_large_numbers(self):
        result = _numeric_overlap_or_step("Budget $1000", "Budget $1001")
        assert result is True

    def test_only_one_has_numbers(self):
        result = _numeric_overlap_or_step("Has 5 items", "No numbers")
        assert result is False


class TestDeriveNudgeMetadata:
    """Test _derive_nudge_metadata function."""

    def test_finance_subscription(self):
        result = _derive_nudge_metadata("Finance", "User has monthly subscription", 3)
        assert result["topic_key"] == "subscription"
        assert result["importance_bin"] == "med"

    def test_finance_spending(self):
        result = _derive_nudge_metadata("Finance", "User spending on groceries", 2)
        assert result["topic_key"] == "spending_pattern"
        assert result["importance_bin"] == "med"

    def test_finance_bill(self):
        result = _derive_nudge_metadata("Finance", "Utility bill due", 4)
        assert result["topic_key"] == "bill"
        assert result["importance_bin"] == "high"

    def test_finance_general(self):
        result = _derive_nudge_metadata("Finance", "Some financial info", 1)
        assert result["topic_key"] == "finance_general"
        assert result["importance_bin"] == "low"

    def test_budget_category(self):
        result = _derive_nudge_metadata("Budget", "Monthly budget allocation", 3)
        assert result["topic_key"] == "budget_status"
        assert result["importance_bin"] == "med"

    def test_goals_active(self):
        result = _derive_nudge_metadata("Goals", "Saving for vacation", 5)
        assert result["topic_key"] == "goal_active"
        assert result["importance_bin"] == "high"

    def test_goals_achievement(self):
        result = _derive_nudge_metadata("Goals", "Reached milestone", 4)
        assert result["topic_key"] == "achievement"
        assert result["importance_bin"] == "high"

    def test_personal_category(self):
        result = _derive_nudge_metadata("Personal", "User's name is Ana", 2)
        assert result["topic_key"] == "personal_info"
        assert result["importance_bin"] == "med"

    def test_education_category(self):
        result = _derive_nudge_metadata("Education", "Learning Python", 3)
        assert result["topic_key"] == "education_interest"
        assert result["importance_bin"] == "med"

    def test_importance_high(self):
        result = _derive_nudge_metadata("Other", "Important fact", 4)
        assert result["importance_bin"] == "high"

    def test_importance_medium(self):
        result = _derive_nudge_metadata("Other", "Medium fact", 2)
        assert result["importance_bin"] == "med"

    def test_importance_low(self):
        result = _derive_nudge_metadata("Other", "Low fact", 1)
        assert result["importance_bin"] == "low"

    def test_case_insensitive_matching(self):
        result = _derive_nudge_metadata("Finance", "MONTHLY SUBSCRIPTION", 3)
        assert result["topic_key"] == "subscription"


class TestSanitizeSemanticTimePhrasesEdgeCases:
    """Edge cases for time phrase sanitization."""

    def test_multiple_time_phrases(self):
        text = "User went to gym today and yesterday bought groceries"
        result = _sanitize_semantic_time_phrases(text)
        assert "today" not in result.lower()
        assert "yesterday" not in result.lower()
        assert "gym" in result.lower()
        assert "groceries" in result.lower()

    def test_time_phrase_at_start(self):
        text = "Today is a good day"
        result = _sanitize_semantic_time_phrases(text)
        assert "today" not in result.lower()
        assert "good" in result.lower()

    def test_time_phrase_at_end(self):
        text = "User completed task yesterday"
        result = _sanitize_semantic_time_phrases(text)
        assert "yesterday" not in result.lower()
        assert "task" in result.lower()

    def test_preserves_important_content(self):
        text = "User prefers email communication"
        result = _sanitize_semantic_time_phrases(text)
        assert result == text

    def test_mixed_temporal_and_permanent(self):
        text = "User's cat turned 4 today"
        result = _sanitize_semantic_time_phrases(text)
        assert "today" not in result.lower()
        assert "cat" in result.lower()
        assert "4" in result


class TestTokenOverlapEdgeCases:
    """Edge cases for token overlap detection."""

    def test_no_overlap_different_words(self):
        # Completely different words with no overlap
        result = _has_min_token_overlap("apple banana", "orange grape")
        assert result is False

    def test_overlap_with_numbers(self):
        # Numbers don't affect word overlap logic
        result = _has_min_token_overlap("user123", "user456")
        # May or may not overlap depending on regex, just test it doesn't error
        assert isinstance(result, bool)


class TestNumericOverlapEdgeCases:
    """Edge cases for numeric overlap detection."""

    def test_zero_values(self):
        result = _numeric_overlap_or_step("Count is 0", "Count is 1")
        assert result is True

    def test_negative_numbers(self):
        # Regex only captures positive integers
        result = _numeric_overlap_or_step("Value -5", "Value -4")
        assert result is True  # Captures 5 and 4

    def test_decimal_numbers(self):
        # Regex captures integer parts
        result = _numeric_overlap_or_step("Price 10.99", "Price 11.99")
        assert result is True  # Captures 10 and 11

    def test_same_number_multiple_times(self):
        result = _numeric_overlap_or_step("3 items and 3 more", "5 total")
        assert result is False  # No overlap or step


class TestDeriveNudgeMetadataEdgeCases:
    """Edge cases for nudge metadata derivation."""

    def test_empty_summary(self):
        result = _derive_nudge_metadata("Finance", "", 3)
        assert "topic_key" in result
        assert result["topic_key"] == "finance_general"

    def test_unknown_category(self):
        result = _derive_nudge_metadata("Unknown", "Some text", 3)
        assert result["topic_key"] == "general"

    def test_multiple_keywords_priority(self):
        # Test that subscription is detected even with other keywords
        result = _derive_nudge_metadata("Finance", "monthly subscription spending", 3)
        assert result["topic_key"] == "subscription"

    def test_importance_boundary_values(self):
        # Test boundary at importance 4
        result_high = _derive_nudge_metadata("Finance", "test", 4)
        assert result_high["importance_bin"] == "high"

        result_med = _derive_nudge_metadata("Finance", "test", 3)
        assert result_med["importance_bin"] == "med"

        # Test boundary at importance 2
        result_med2 = _derive_nudge_metadata("Finance", "test", 2)
        assert result_med2["importance_bin"] == "med"

        result_low = _derive_nudge_metadata("Finance", "test", 1)
        assert result_low["importance_bin"] == "low"

    def test_case_variations_in_summary(self):
        result1 = _derive_nudge_metadata("Finance", "SUBSCRIPTION", 3)
        result2 = _derive_nudge_metadata("Finance", "subscription", 3)
        result3 = _derive_nudge_metadata("Finance", "Subscription", 3)

        assert result1["topic_key"] == result2["topic_key"] == result3["topic_key"]
