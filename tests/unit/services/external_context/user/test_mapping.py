"""Tests for external_context/user/mapping.py - AI context transformation."""

import uuid

import pytest

from app.models.user import SubscriptionTier, UserContext
from app.services.external_context.user.mapping import (
    _merge_summary_into_context,
    _normalize_income_range,
    map_ai_context_to_user_context,
    map_user_context_to_ai_context,
)


@pytest.fixture
def test_user_id():
    """Provide a valid UUID for UserContext."""
    return str(uuid.uuid4())


class TestNormalizeIncomeRange:
    """Test _normalize_income_range normalization logic."""

    def test_none_returns_none(self):
        """Should return None for None input."""
        assert _normalize_income_range(None) is None

    def test_empty_string_returns_none(self):
        """Should return None for empty string."""
        assert _normalize_income_range("") is None

    def test_removes_dollar_and_commas(self):
        """Should remove $ and comma symbols."""
        assert _normalize_income_range("$50,000-$75,000") == "50000_75000"

    def test_handles_100k_plus_special_case(self):
        """Should return 'over_100k' for 100k+ variations."""
        assert _normalize_income_range("100k+") == "over_100k"
        assert _normalize_income_range("$100k+") == "over_100k"
        assert _normalize_income_range("100k plus") == "over_100k"

    def test_handles_greater_than_100k(self):
        """Should handle > prefix for 100k."""
        assert _normalize_income_range(">100k") == "over_100k"

    def test_handles_plus_for_non_100k(self):
        """Should convert + to _plus for non-100k values."""
        assert _normalize_income_range("75k+") == "75k_plus"

    def test_replaces_dashes_and_spaces(self):
        """Should convert dashes and spaces to underscores."""
        assert _normalize_income_range("50k-75k") == "50k_75k"
        assert _normalize_income_range("50k 75k") == "50k_75k"

    def test_lowercase_conversion(self):
        """Should convert to lowercase."""
        assert _normalize_income_range("50K-75K") == "50k_75k"


class TestMergeSummaryIntoContext:
    """Test _merge_summary_into_context merging logic."""

    def test_merges_flat_fields(self, test_user_id):
        """Should merge flat fields from summary to user context."""
        user_ctx = UserContext(user_id=test_user_id)
        summary = {"preferred_name": "John", "age": 30, "city": "NYC"}

        _merge_summary_into_context(summary, user_ctx)

        assert user_ctx.preferred_name == "John"
        assert user_ctx.age == 30
        assert user_ctx.city == "NYC"

    def test_merges_list_fields(self, test_user_id):
        """Should merge list fields correctly."""
        user_ctx = UserContext(user_id=test_user_id)
        summary = {
            "money_feelings": ["anxious", "hopeful"],
            "learning_interests": ["investing", "budgeting"],
        }

        _merge_summary_into_context(summary, user_ctx)

        assert user_ctx.money_feelings == ["anxious", "hopeful"]
        assert user_ctx.learning_interests == ["investing", "budgeting"]

    def test_merges_nested_identity_fields(self, test_user_id):
        """Should merge nested identity object."""
        user_ctx = UserContext(user_id=test_user_id)
        summary = {"identity": {"preferred_name": "Jane", "pronouns": "she/her", "age": 28, "birth_date": "1995-05-01"}}

        _merge_summary_into_context(summary, user_ctx)

        assert user_ctx.identity.preferred_name == "Jane"
        assert user_ctx.identity.pronouns == "she/her"
        assert user_ctx.identity.age == 28
        assert user_ctx.identity.birth_date == "1995-05-01"

    def test_merges_nested_style_fields(self, test_user_id):
        """Should merge nested style preferences."""
        user_ctx = UserContext(user_id=test_user_id)
        summary = {"style": {"tone": "casual", "verbosity": "detailed"}}

        _merge_summary_into_context(summary, user_ctx)

        assert user_ctx.style.tone == "casual"
        assert user_ctx.style.verbosity == "detailed"

    def test_ignores_subscription_tier_field(self, test_user_id):
        """Should leave subscription tier unchanged when summary includes it."""
        user_ctx = UserContext(user_id=test_user_id)
        summary = {"subscription_tier": "paid"}

        _merge_summary_into_context(summary, user_ctx)

        assert user_ctx.subscription_tier == SubscriptionTier.FREE

    def test_ignores_tier_string_field(self, test_user_id):
        """Should leave tier unset when summary includes legacy tier."""
        user_ctx = UserContext(user_id=test_user_id)
        summary = {"tier": "premium"}

        _merge_summary_into_context(summary, user_ctx)

        assert user_ctx.tier is None

    def test_skips_none_values(self, test_user_id):
        """Should not overwrite with None values."""
        user_ctx = UserContext(user_id=test_user_id, preferred_name="Original")
        summary = {"preferred_name": None}

        _merge_summary_into_context(summary, user_ctx)

        assert user_ctx.preferred_name == "Original"


class TestMapAIContextToUserContext:
    """Test map_ai_context_to_user_context transformation."""

    def test_maps_user_context_summary(self, test_user_id):
        """Should extract and merge user_context_summary."""
        ai_context = {"user_context_summary": {"preferred_name": "Alice", "age": 25, "city": "Boston"}}
        user_ctx = UserContext(user_id=test_user_id)

        result = map_ai_context_to_user_context(ai_context, user_ctx)

        assert result.preferred_name == "Alice"
        assert result.age == 25
        assert result.city == "Boston"

    def test_maps_preferred_name_from_top_level(self, test_user_id):
        """Should use top-level preferred_name when context is empty."""
        ai_context = {"preferred_name": "Bob"}
        user_ctx = UserContext(user_id=test_user_id)

        result = map_ai_context_to_user_context(ai_context, user_ctx)

        assert result.preferred_name == "Bob"

    def test_does_not_overwrite_existing_preferred_name(self, test_user_id):
        """Should not overwrite existing preferred_name."""
        ai_context = {"preferred_name": "Bob"}
        user_ctx = UserContext(user_id=test_user_id, preferred_name="Alice")

        result = map_ai_context_to_user_context(ai_context, user_ctx)

        assert result.preferred_name == "Alice"

    def test_maps_communication_style_tone(self, test_user_id):
        """Should map communication_style.tone to both fields."""
        ai_context = {"communication_style": {"tone": "friendly"}}
        user_ctx = UserContext(user_id=test_user_id)

        result = map_ai_context_to_user_context(ai_context, user_ctx)

        assert result.style.tone == "friendly"
        assert result.tone_preference == "friendly"

    def test_maps_goals_tracking_to_goals(self, test_user_id):
        """Should extract goal names from goals_tracking."""
        ai_context = {"goals_tracking": {"retirement": {}, "house": {}}}
        user_ctx = UserContext(user_id=test_user_id)

        result = map_ai_context_to_user_context(ai_context, user_ctx)

        assert "retirement" in result.goals
        assert "house" in result.goals

    def test_maps_financial_context_income_range(self, test_user_id):
        """Should normalize and map financial_context.income_range."""
        ai_context = {"financial_context": {"income_range": "$50,000-$75,000"}}
        user_ctx = UserContext(user_id=test_user_id)

        result = map_ai_context_to_user_context(ai_context, user_ctx)

        assert result.income == "50000_75000"
        assert result.income_band == "50000_75000"

    def test_maps_learning_data_completed_topics(self, test_user_id):
        """Should append completed_topics to learning_interests."""
        ai_context = {"learning_data": {"completed_topics": ["stocks", "bonds"]}}
        user_ctx = UserContext(user_id=test_user_id)

        result = map_ai_context_to_user_context(ai_context, user_ctx)

        assert "stocks" in result.learning_interests
        assert "bonds" in result.learning_interests

    def test_avoids_duplicate_learning_topics(self, test_user_id):
        """Should not add duplicate topics to learning_interests."""
        ai_context = {"learning_data": {"completed_topics": ["stocks", "bonds"]}}
        user_ctx = UserContext(user_id=test_user_id, learning_interests=["stocks"])

        result = map_ai_context_to_user_context(ai_context, user_ctx)

        assert result.learning_interests.count("stocks") == 1
        assert "bonds" in result.learning_interests


class TestMapUserContextToAIContext:
    """Test map_user_context_to_ai_context reverse transformation."""

    def test_maps_preferred_name(self, test_user_id):
        """Should map preferred_name to output."""
        user_ctx = UserContext(user_id=test_user_id, preferred_name="Charlie")

        result = map_user_context_to_ai_context(user_ctx)

        assert result["preferred_name"] == "Charlie"

    def test_maps_style_tone_to_communication_style(self, test_user_id):
        """Should map style.tone to communication_style."""
        user_ctx = UserContext(user_id=test_user_id)
        user_ctx.style.tone = "friendly"

        result = map_user_context_to_ai_context(user_ctx)

        assert result["communication_style"]["tone"] == "friendly"

    def test_maps_goals_to_goals_tracking(self, test_user_id):
        """Should map goals list to goals_tracking dict."""
        user_ctx = UserContext(user_id=test_user_id, goals=["retirement", "house"])

        result = map_user_context_to_ai_context(user_ctx)

        assert result["goals_tracking"] == {"retirement": {}, "house": {}}

    def test_maps_income_to_financial_context(self, test_user_id):
        """Should map income to financial_context.income_range."""
        user_ctx = UserContext(user_id=test_user_id, income="75k_100k")

        result = map_user_context_to_ai_context(user_ctx)

        assert result["financial_context"]["income_range"] == "75k_100k"

    def test_includes_user_context_summary(self, test_user_id):
        """Should include full user_context_summary in output."""
        user_ctx = UserContext(user_id=test_user_id, preferred_name="Test", age=30)

        result = map_user_context_to_ai_context(user_ctx)

        assert "user_context_summary" in result
        assert isinstance(result["user_context_summary"], dict)

    def test_sets_onboarding_completed_from_ready_for_orchestrator(self, test_user_id):
        """Should map ready_for_orchestrator to onboarding_completed."""
        user_ctx = UserContext(user_id=test_user_id, ready_for_orchestrator=True)

        result = map_user_context_to_ai_context(user_ctx)

        assert result["onboarding_completed"] is True

    def test_sets_is_active_to_true(self, test_user_id):
        """Should always set is_active to True."""
        user_ctx = UserContext(user_id=test_user_id)

        result = map_user_context_to_ai_context(user_ctx)

        assert result["is_active"] is True

    def test_ensures_all_expected_keys_exist(self, test_user_id):
        """Should ensure all expected keys exist in output."""
        user_ctx = UserContext(user_id=test_user_id)

        result = map_user_context_to_ai_context(user_ctx)

        expected_keys = [
            "financial_context",
            "communication_style",
            "goals_tracking",
            "learning_data",
        ]
        for key in expected_keys:
            assert key in result
            assert isinstance(result[key], dict)
