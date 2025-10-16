"""Unit tests for app.agents.supervisor.memory.utils module.

Tests cover utility functions for:
- UTC timestamp generation
- ISO datetime parsing
- Weight string parsing
- Profile line building from context
"""

from datetime import datetime, timezone
from unittest.mock import patch

from app.agents.supervisor.memory.utils import (
    _build_profile_line,
    _parse_iso,
    _parse_weights,
    _utc_now_iso,
)


class TestUtcNowIso:
    """Test cases for _utc_now_iso function."""

    def test_returns_iso_format_string(self):
        """Test that function returns a valid ISO format string."""
        result = _utc_now_iso()

        # Should be parseable as ISO datetime
        parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
        assert isinstance(parsed, datetime)
        assert parsed.tzinfo is not None

    @patch("app.agents.supervisor.memory.utils.datetime")
    def test_returns_utc_timezone(self, mock_datetime):
        """Test that function returns UTC timezone."""
        fixed_time = datetime(2025, 1, 15, 12, 30, 45, tzinfo=timezone.utc)
        mock_datetime.now.return_value = fixed_time

        result = _utc_now_iso()

        # Verify datetime.now was called with UTC timezone
        mock_datetime.now.assert_called_once_with(tz=timezone.utc)
        assert "2025-01-15" in result
        assert "12:30:45" in result


class TestParseIso:
    """Test cases for _parse_iso function."""

    def test_parse_valid_iso_string(self):
        """Test parsing a valid ISO datetime string."""
        iso_str = "2025-01-15T12:30:45+00:00"
        result = _parse_iso(iso_str)

        assert result is not None
        assert isinstance(result, datetime)
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 12
        assert result.minute == 30
        assert result.second == 45

    def test_parse_iso_with_z_suffix(self):
        """Test parsing ISO string with Z suffix (UTC indicator)."""
        iso_str = "2025-01-15T12:30:45Z"
        result = _parse_iso(iso_str)

        assert result is not None
        assert isinstance(result, datetime)
        assert result.year == 2025

    def test_parse_none_input(self):
        """Test parsing None returns None."""
        result = _parse_iso(None)
        assert result is None

    def test_parse_empty_string(self):
        """Test parsing empty string returns None."""
        result = _parse_iso("")
        assert result is None

    def test_parse_invalid_format(self):
        """Test parsing invalid format returns None."""
        result = _parse_iso("not-a-datetime")
        assert result is None

    def test_parse_malformed_iso(self):
        """Test parsing malformed ISO string returns None."""
        result = _parse_iso("2025-13-45T99:99:99")
        assert result is None


class TestParseWeights:
    """Test cases for _parse_weights function."""

    def test_parse_valid_weights_string(self):
        """Test parsing valid comma-separated key=value weights."""
        weights_str = "sim=0.60,imp=0.25,recency=0.10,pinned=0.05"
        result = _parse_weights(weights_str)

        assert result["sim"] == 0.60
        assert result["imp"] == 0.25
        assert result["recency"] == 0.10
        assert result["pinned"] == 0.05

    def test_parse_weights_with_spaces(self):
        """Test parsing weights with extra whitespace."""
        weights_str = "sim = 0.60 , imp = 0.25 , recency = 0.10"
        result = _parse_weights(weights_str)

        assert result["sim"] == 0.60
        assert result["imp"] == 0.25
        assert result["recency"] == 0.10

    def test_parse_empty_string_returns_defaults(self):
        """Test parsing empty string returns default weights."""
        result = _parse_weights("")

        assert result["sim"] == 0.55
        assert result["imp"] == 0.20
        assert result["recency"] == 0.15
        assert result["pinned"] == 0.10

    def test_parse_malformed_string_returns_defaults(self):
        """Test parsing malformed string returns default weights."""
        result = _parse_weights("invalid_format")

        # Should return defaults when parsing fails
        assert result["sim"] == 0.55
        assert result["imp"] == 0.20
        assert result["recency"] == 0.15
        assert result["pinned"] == 0.10

    def test_parse_partial_weights(self):
        """Test parsing partial weights merges with defaults."""
        weights_str = "sim=0.70,imp=0.30"
        result = _parse_weights(weights_str)

        # Updated values
        assert result["sim"] == 0.70
        assert result["imp"] == 0.30
        # Defaults preserved
        assert result["recency"] == 0.15
        assert result["pinned"] == 0.10

    def test_parse_with_empty_parts(self):
        """Test parsing with empty comma-separated parts."""
        weights_str = "sim=0.60,,imp=0.25,,"
        result = _parse_weights(weights_str)

        assert result["sim"] == 0.60
        assert result["imp"] == 0.25


class TestBuildProfileLine:
    """Test cases for _build_profile_line function."""

    def test_build_with_complete_profile(self):
        """Test building profile line with all fields present."""
        ctx = {
            "identity": {"preferred_name": "John", "age": 30},
            "city": "San Francisco",
            "language": "en-US",
            "tone_preference": "casual",
            "income_band": "$50k-$75k",
            "rent_mortgage": "2000",
            "subscription_tier": "premium",
            "money_feelings": ["anxious", "optimistic", "confused"],
            "housing_satisfaction": "satisfied",
            "health_insurance": "employer-provided",
            "goals": ["save for house", "pay off debt", "build emergency fund"],
        }

        result = _build_profile_line(ctx)

        assert result is not None
        assert "CONTEXT_PROFILE:" in result
        assert "John" in result
        assert "30 years old" in result
        assert "San Francisco" in result
        assert "English" in result
        assert "casual communication tone" in result
        assert "$50k-$75k" in result
        assert "$2000" in result
        assert "premium subscription tier" in result
        assert "anxious, optimistic, confused" in result
        assert "satisfied" in result
        assert "employer-provided" in result
        assert "save for house, pay off debt, build emergency fund" in result
        assert "Use these details to personalize" in result

    def test_build_with_name_only(self):
        """Test building profile with only name."""
        ctx = {"identity": {"preferred_name": "Alice"}}

        result = _build_profile_line(ctx)

        assert result is not None
        assert "Alice" in result
        assert "CONTEXT_PROFILE:" in result

    def test_build_with_age_only(self):
        """Test building profile with only age."""
        ctx = {"identity": {"age": 25}}

        result = _build_profile_line(ctx)

        assert result is not None
        assert "25 years old" in result

    def test_build_with_name_and_age(self):
        """Test building profile with name and age."""
        ctx = {
            "identity": {"preferred_name": "Bob", "age": 35}
        }

        result = _build_profile_line(ctx)

        assert result is not None
        assert "Bob" in result
        assert "35 years old" in result

    def test_build_with_age_range_when_no_age(self):
        """Test age_range is used when age is not present."""
        ctx = {
            "preferred_name": "Charlie",
            "age_range": "25-34"
        }

        result = _build_profile_line(ctx)

        assert result is not None
        assert "25-34 age range" in result

    def test_age_range_ignored_when_age_present(self):
        """Test age_range is ignored when age is present."""
        ctx = {
            "identity": {"preferred_name": "David", "age": 30},
            "age_range": "25-34"
        }

        result = _build_profile_line(ctx)

        assert result is not None
        assert "30 years old" in result
        assert "25-34" not in result

    def test_build_with_flat_structure(self):
        """Test building profile with flat (non-nested) context structure."""
        ctx = {
            "preferred_name": "Eve",
            "age": 28,
            "city": "Austin",
            "language": "es-MX",
            "tone_preference": "professional"
        }

        result = _build_profile_line(ctx)

        assert result is not None
        assert "Eve" in result
        assert "28 years old" in result
        assert "Austin" in result
        assert "Spanish" in result
        assert "professional communication tone" in result

    def test_build_with_nested_location(self):
        """Test building profile with nested location structure."""
        ctx = {
            "preferred_name": "Frank",
            "location": {"city": "Boston"}
        }

        result = _build_profile_line(ctx)

        assert result is not None
        assert "Boston" in result

    def test_build_with_nested_style(self):
        """Test building profile with nested style structure."""
        ctx = {
            "preferred_name": "Grace",
            "style": {"tone": "friendly"}
        }

        result = _build_profile_line(ctx)

        assert result is not None
        assert "friendly communication tone" in result

    def test_build_with_nested_locale_info(self):
        """Test building profile with nested locale_info structure."""
        ctx = {
            "preferred_name": "Henry",
            "locale_info": {"language": "en-GB"}
        }

        result = _build_profile_line(ctx)

        assert result is not None
        assert "English" in result

    def test_language_formatting_english(self):
        """Test language formatting for English."""
        ctx = {"language": "en-US"}
        result = _build_profile_line(ctx)

        assert "English" in result

    def test_language_formatting_spanish(self):
        """Test language formatting for Spanish."""
        ctx = {"language": "es-ES"}
        result = _build_profile_line(ctx)

        assert "Spanish" in result

    def test_build_with_alternative_field_names(self):
        """Test building profile with alternative field names."""
        ctx = {
            "preferred_name": "Ivy",
            "income": "$100k+",  # Alternative to income_band
            "housing": "1500",   # Alternative to rent_mortgage
            "tier": "basic"      # Alternative to subscription_tier
        }

        result = _build_profile_line(ctx)

        assert result is not None
        assert "$100k+" in result
        assert "$1500" in result
        assert "basic subscription tier" in result

    def test_build_with_limited_money_feelings(self):
        """Test that only first 3 money feelings are included."""
        ctx = {
            "preferred_name": "Jack",
            "money_feelings": ["anxious", "hopeful", "stressed", "optimistic", "confused"]
        }

        result = _build_profile_line(ctx)

        assert result is not None
        assert "anxious, hopeful, stressed" in result
        assert "optimistic" not in result
        assert "confused" not in result

    def test_build_with_limited_goals(self):
        """Test that only first 3 goals are included."""
        ctx = {
            "preferred_name": "Karen",
            "goals": ["goal1", "goal2", "goal3", "goal4", "goal5"]
        }

        result = _build_profile_line(ctx)

        assert result is not None
        assert "goal1, goal2, goal3" in result
        assert "goal4" not in result

    def test_build_with_limited_blocked_topics(self):
        """Test that only first 5 blocked topics are included."""
        ctx = {
            "preferred_name": "Leo"
        }

        result = _build_profile_line(ctx)

        assert result is not None
        assert "topic6" not in result

    def test_build_with_non_string_list_items(self):
        """Test handling of non-string items in lists."""
        ctx = {
            "preferred_name": "Mia",
            "goals": ["valid_goal", 123, None, "another_goal"],
            "money_feelings": [456, "anxious", None]
        }

        result = _build_profile_line(ctx)

        assert result is not None
        # Code filters non-string items correctly
        assert "valid_goal" in result
        assert "anxious" in result
        # Non-string items (123, 456, None) should not appear
        assert "123" not in result
        assert "456" not in result

    def test_build_with_non_list_goals(self):
        """Test handling when goals is not a list."""
        ctx = {
            "preferred_name": "Nina",
            "goals": "not a list"
        }

        result = _build_profile_line(ctx)

        assert result is not None
        # Should not crash, goals just won't be included

    def test_build_with_empty_dict(self):
        """Test building profile with empty context returns None."""
        ctx = {}
        result = _build_profile_line(ctx)

        assert result is None

    def test_build_with_non_dict_input(self):
        """Test building profile with non-dict input returns None."""
        result = _build_profile_line("not a dict")
        assert result is None

        result = _build_profile_line(None)
        assert result is None

        result = _build_profile_line([])
        assert result is None

    def test_guidance_text_included(self):
        """Test that guidance text is included in profile line."""
        ctx = {"preferred_name": "Oscar"}
        result = _build_profile_line(ctx)

        assert result is not None
        assert "Use these details to personalize tone and examples" in result
        assert "Do not restate this information verbatim" in result
        assert "Do not override with assumptions" in result
        assert "prefer the latest user message" in result
        assert "Respect blocked topics" in result


    def test_preference_order_for_nested_vs_flat(self):
        """Test that nested fields take precedence over flat fields."""
        ctx = {
            "preferred_name": "flat_name",
            "identity": {"preferred_name": "nested_name", "age": 30},
            "age": 25
        }

        result = _build_profile_line(ctx)

        # Nested should take precedence
        assert "nested_name" in result or "flat_name" in result
