"""Tests for llm/stub.py - Stub LLM implementation for local development."""

import pytest

from app.services.llm.stub import StubLLM


@pytest.fixture
def stub_llm():
    """Create StubLLM instance for testing."""
    return StubLLM()


class TestStubLLMExtract:
    """Test StubLLM.extract() naive extraction logic."""

    def test_extracts_preferred_name_from_first_word(self, stub_llm):
        """Should extract first word as preferred_name when schema mentions it."""
        schema = {"preferred_name": "string"}
        text = "John Smith"

        result = stub_llm.extract(schema, text)

        assert result["preferred_name"] == "John"

    def test_extracts_name_with_punctuation_removed(self, stub_llm):
        """Should remove trailing punctuation from extracted name."""
        schema = {"preferred_name": "string"}
        text = "Alice, how are you?"

        result = stub_llm.extract(schema, text)

        assert result["preferred_name"] == "Alice"

    def test_extracts_tone_concise(self, stub_llm):
        """Should detect 'concise' tone from keywords (concise/direct)."""
        schema = {}

        # Test "concise" keyword
        result = stub_llm.extract(schema, "Keep it concise please")
        assert result["tone"] == "concise"

        # Test "direct" keyword (also sets concise)
        result = stub_llm.extract(schema, "Be direct with me")
        assert result["tone"] == "concise"

    def test_extracts_tone_warm(self, stub_llm):
        """Should detect 'warm' tone from keywords."""
        schema = {}
        text = "I prefer warm and conversational"

        result = stub_llm.extract(schema, text)

        assert result["tone"] == "warm"

    def test_extracts_blocked_categories(self, stub_llm):
        """Should extract blocked categories from various phrases."""
        schema = {}

        # Test "avoid" phrase
        result = stub_llm.extract(schema, "I want to avoid politics and religion")
        assert "blocked_categories" in result
        assert "politics" in result["blocked_categories"]
        assert "religion" in result["blocked_categories"]

        # Test "don't want to discuss" phrase
        result = stub_llm.extract(schema, "I don't want to discuss sports")
        assert "blocked_categories" in result
        assert "sports" in result["blocked_categories"]

    def test_extracts_mood_from_feeling_keyword(self, stub_llm):
        """Should extract mood when 'feeling' keyword present."""
        schema = {}
        text = "I'm feeling stressed"

        result = stub_llm.extract(schema, text)

        assert result["mood"] == "I'm feeling stressed"

    def test_extracts_mood_from_predefined_words(self, stub_llm):
        """Should extract mood from predefined emotional words."""
        schema = {}

        # Test sample predefined mood words
        for mood in ["stressed", "optimistic"]:
            result = stub_llm.extract(schema, mood)
            assert result["mood"] == mood

    def test_extracts_city_from_in_pattern(self, stub_llm):
        """Should extract city name from 'in [City]' pattern."""
        schema = {}
        text = "I live in Seattle"

        result = stub_llm.extract(schema, text)

        assert result["city"] == "Seattle"

    def test_extracts_dependents_from_numbers(self, stub_llm):
        """Should extract first number as dependents."""
        schema = {}
        text = "I have 3 children"

        result = stub_llm.extract(schema, text)

        assert result["dependents"] == 3

    def test_extracts_primary_financial_goal(self, stub_llm):
        """Should extract financial goal from various patterns."""
        schema = {}

        # Test "goal" keyword
        result = stub_llm.extract(schema, "My goal is to buy a house")
        assert result["primary_financial_goal"] == "My goal is to buy a house"

        # Test "pay" prefix
        result = stub_llm.extract(schema, "pay off debt")
        assert result["primary_financial_goal"] == "pay off debt"

        # Test "save" prefix
        result = stub_llm.extract(schema, "save for retirement")
        assert result["primary_financial_goal"] == "save for retirement"

    def test_extracts_income_indicator(self, stub_llm):
        """Should detect income mention with various indicators."""
        schema = {}

        # Test "k" suffix
        result = stub_llm.extract(schema, "I earn 50k per year")
        assert result["income"] == "provided"

        # Test dollar sign
        result = stub_llm.extract(schema, "My salary is $60000")
        assert result["income"] == "provided"

    def test_extracts_opt_in(self, stub_llm):
        """Should extract opt_in boolean from affirmative/negative responses."""
        schema = {}

        # Test affirmative responses
        for response in ["yes", "sure", "okay"]:
            result = stub_llm.extract(schema, response)
            assert result["opt_in"] is True

        # Test negative responses
        for response in ["no", "nope"]:
            result = stub_llm.extract(schema, response)
            assert result["opt_in"] is False

    def test_extracts_multiple_fields_simultaneously(self, stub_llm):
        """Should extract multiple fields from single text."""
        schema = {"preferred_name": "string"}
        text = "Alice feeling optimistic in Boston with 2 kids, wants to save for college"

        result = stub_llm.extract(schema, text)

        # Should extract name, city, and dependents
        assert result["preferred_name"] == "Alice"
        assert result["mood"] == text.strip()  # Mood gets the full text
        assert result["city"] == "Boston"
        assert result["dependents"] == 2
        # Note: primary_financial_goal requires "goal", "pay ", or "save " at start
        # This text has "wants to save" which doesn't match the pattern
