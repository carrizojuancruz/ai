"""Unit tests for finance agent business rules."""

from app.agents.supervisor.finance_agent.business_rules import (
    CATEGORY_GROUPS,
    PLAID_PRIMARY_CATEGORIES,
    get_business_rules_context_str,
)


class TestBusinessRulesConstants:
    """Test business rules constants."""

    def test_plaid_primary_categories(self):
        """Test PLAID_PRIMARY_CATEGORIES contains expected categories."""
        expected_categories = [
            "INCOME", "TRANSFER_IN", "TRANSFER_OUT",
            "LOAN_PAYMENTS", "BANK_FEES",
            "ENTERTAINMENT", "FOOD_AND_DRINK", "GENERAL_MERCHANDISE",
            "HOME_IMPROVEMENT", "MEDICAL", "PERSONAL_CARE",
            "GENERAL_SERVICES", "GOVERNMENT_AND_NON_PROFIT",
            "TRANSPORTATION", "TRAVEL", "RENT_AND_UTILITIES"
        ]

        for category in expected_categories:
            assert category in PLAID_PRIMARY_CATEGORIES

    def test_category_groups_structure(self):
        """Test CATEGORY_GROUPS has expected structure."""
        assert isinstance(CATEGORY_GROUPS, dict)
        assert len(CATEGORY_GROUPS) > 0

        # Check that each group has a list of categories
        for _group, categories in CATEGORY_GROUPS.items():
            assert isinstance(categories, list)
            assert len(categories) > 0

    def test_category_groups_common_categories(self):
        """Test that common categories are present in groups."""
        assert "income" in CATEGORY_GROUPS
        assert "INCOME" in CATEGORY_GROUPS["income"]

        assert "food_and_drink" in CATEGORY_GROUPS
        assert "FOOD_AND_DRINK" in CATEGORY_GROUPS["food_and_drink"]

        assert "entertainment" in CATEGORY_GROUPS
        assert "ENTERTAINMENT" in CATEGORY_GROUPS["entertainment"]


class TestGetBusinessRulesContextStr:
    """Test get_business_rules_context_str function."""

    def test_context_string_complete_structure(self):
        """Test that context string has all expected sections and content."""
        context = get_business_rules_context_str()

        # Verify structure sections
        assert "Plaid PRIMARY Categories:" in context
        assert "Category Groups:" in context
        assert "Common Query Patterns:" in context
        assert "Fallback Handling:" in context

        # Verify primary categories included
        for category in PLAID_PRIMARY_CATEGORIES[:5]:
            assert category in context

        # Verify query patterns included
        assert "food spending" in context
        assert "FOOD_AND_DRINK" in context
        assert "shopping expenses" in context
        assert "GENERAL_MERCHANDISE" in context

        # Verify reasonable length
        assert len(context) > 200
