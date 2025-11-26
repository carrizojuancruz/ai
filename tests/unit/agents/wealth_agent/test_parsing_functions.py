"""Tests for parsing functions in wealth agent subgraph."""

import pytest

from app.agents.supervisor.wealth_agent.subgraph import (
    parse_used_sources,
    parse_used_subcategories,
)


@pytest.mark.unit
class TestParseUsedSources:
    """Test suite for parse_used_sources function."""

    def test_parse_valid_sources_list(self):
        """Test parsing valid USED_SOURCES with proper JSON array."""
        content = 'Analysis\n\nUSED_SOURCES: ["http://example.com/1", "http://example.com/2"]'
        result = parse_used_sources(content)

        assert len(result) == 2
        assert result[0] == "http://example.com/1"
        assert result[1] == "http://example.com/2"

    def test_parse_sources_with_bold_marker(self):
        """Test parsing USED_SOURCES with markdown bold markers."""
        content = 'Analysis\n\n**USED_SOURCES:** ["http://example.com/1"]'
        result = parse_used_sources(content)

        assert len(result) == 1
        assert result[0] == "http://example.com/1"

    def test_parse_sources_single_url(self):
        """Test parsing single URL in USED_SOURCES."""
        content = 'USED_SOURCES: ["http://single.com"]'
        result = parse_used_sources(content)

        assert len(result) == 1
        assert result[0] == "http://single.com"

    def test_parse_sources_empty_array(self):
        """Test parsing empty USED_SOURCES array."""
        content = 'Analysis\n\nUSED_SOURCES: []'
        result = parse_used_sources(content)

        assert result == []

    def test_parse_sources_with_whitespace(self):
        """Test parsing handles extra whitespace in JSON."""
        content = 'USED_SOURCES: [  "http://example.com/1"  ,  "http://example.com/2"  ]'
        result = parse_used_sources(content)

        assert len(result) == 2

    def test_parse_sources_filters_empty_strings(self):
        """Test parsing filters out empty strings."""
        content = 'USED_SOURCES: ["http://valid.com", "", "  ", "http://another.com"]'
        result = parse_used_sources(content)

        assert len(result) == 2
        assert result[0] == "http://valid.com"
        assert result[1] == "http://another.com"

    def test_parse_sources_filters_non_strings(self):
        """Test parsing filters out non-string values."""
        content = 'USED_SOURCES: ["http://valid.com", 123, null, true, "http://another.com"]'
        result = parse_used_sources(content)

        assert len(result) == 2
        assert result[0] == "http://valid.com"
        assert result[1] == "http://another.com"

    def test_parse_sources_no_marker_found(self):
        """Test returns empty list when USED_SOURCES marker not found."""
        content = 'Just some regular analysis text without the marker'
        result = parse_used_sources(content)

        assert result == []

    def test_parse_sources_malformed_json(self):
        """Test handles malformed JSON gracefully."""
        content = 'USED_SOURCES: [invalid json syntax'
        result = parse_used_sources(content)

        assert result == []

    def test_parse_sources_invalid_json_format(self):
        """Test handles invalid JSON structures."""
        content = 'USED_SOURCES: {"url": "http://example.com"}'
        result = parse_used_sources(content)

        assert result == []

    def test_parse_sources_multiline_with_newlines(self):
        """Test parsing works with multiline content."""
        content = '''Some analysis text here.

**USED_SOURCES:** ["http://example.com/1", "http://example.com/2"]

More analysis below.'''
        result = parse_used_sources(content)

        assert len(result) == 2

    def test_parse_sources_with_special_characters(self):
        """Test parsing handles URLs with special characters."""
        content = 'USED_SOURCES: ["http://example.com/path?query=value&other=123", "http://example.com/#anchor"]'
        result = parse_used_sources(content)

        assert len(result) == 2
        assert "query=value" in result[0]
        assert "#anchor" in result[1]

    def test_parse_sources_case_sensitive_marker(self):
        """Test marker is case-sensitive (lowercase should not match)."""
        content = 'used_sources: ["http://example.com"]'
        result = parse_used_sources(content)

        assert result == []

    def test_parse_sources_empty_string_input(self):
        """Test handles empty string input."""
        result = parse_used_sources("")

        assert result == []

    def test_parse_sources_with_escaped_quotes(self):
        """Test parsing handles escaped quotes in URLs."""
        content = r'USED_SOURCES: ["http://example.com/path\"with\"quotes"]'
        result = parse_used_sources(content)

        assert isinstance(result, list)


@pytest.mark.unit
class TestParseUsedSubcategories:
    """Test suite for parse_used_subcategories function."""

    def test_parse_valid_subcategories_list(self):
        """Test parsing valid USED_SUBCATEGORIES with proper JSON array."""
        content = 'Analysis\n\nUSED_SUBCATEGORIES: ["reports", "profile"]'
        result = parse_used_subcategories(content)

        assert len(result) == 2
        assert result[0] == "reports"
        assert result[1] == "profile"

    def test_parse_subcategories_with_bold_marker(self):
        """Test parsing USED_SUBCATEGORIES with markdown bold markers."""
        content = 'Analysis\n\n**USED_SUBCATEGORIES:** ["connect-account"]'
        result = parse_used_subcategories(content)

        assert len(result) == 1
        assert result[0] == "connect-account"

    def test_parse_subcategories_single_value(self):
        """Test parsing single subcategory in USED_SUBCATEGORIES."""
        content = 'USED_SUBCATEGORIES: ["reports"]'
        result = parse_used_subcategories(content)

        assert len(result) == 1
        assert result[0] == "reports"

    def test_parse_subcategories_empty_array(self):
        """Test parsing empty USED_SUBCATEGORIES array."""
        content = 'Analysis\n\nUSED_SUBCATEGORIES: []'
        result = parse_used_subcategories(content)

        assert result == []

    def test_parse_subcategories_with_whitespace(self):
        """Test parsing handles extra whitespace in JSON."""
        content = 'USED_SUBCATEGORIES: [  "reports"  ,  "profile"  ]'
        result = parse_used_subcategories(content)

        assert len(result) == 2

    def test_parse_subcategories_filters_empty_strings(self):
        """Test parsing filters out empty strings."""
        content = 'USED_SUBCATEGORIES: ["reports", "", "  ", "profile"]'
        result = parse_used_subcategories(content)

        assert len(result) == 2
        assert result[0] == "reports"
        assert result[1] == "profile"

    def test_parse_subcategories_filters_non_strings(self):
        """Test parsing filters out non-string values."""
        content = 'USED_SUBCATEGORIES: ["reports", 123, null, true, "profile"]'
        result = parse_used_subcategories(content)

        assert len(result) == 2
        assert result[0] == "reports"
        assert result[1] == "profile"

    def test_parse_subcategories_no_marker_found(self):
        """Test returns empty list when USED_SUBCATEGORIES marker not found."""
        content = 'Just some regular analysis text without the marker'
        result = parse_used_subcategories(content)

        assert result == []

    def test_parse_subcategories_malformed_json(self):
        """Test handles malformed JSON gracefully."""
        content = 'USED_SUBCATEGORIES: [invalid json syntax'
        result = parse_used_subcategories(content)

        assert result == []

    def test_parse_subcategories_invalid_json_format(self):
        """Test handles invalid JSON structures."""
        content = 'USED_SUBCATEGORIES: {"category": "reports"}'
        result = parse_used_subcategories(content)

        assert result == []

    def test_parse_subcategories_multiline_with_newlines(self):
        """Test parsing works with multiline content."""
        content = '''Some analysis text here.

**USED_SUBCATEGORIES:** ["reports", "profile"]

More analysis below.'''
        result = parse_used_subcategories(content)

        assert len(result) == 2

    def test_parse_subcategories_with_duplicates(self):
        """Test parsing preserves duplicates for frequency counting."""
        content = 'USED_SUBCATEGORIES: ["reports", "reports", "profile"]'
        result = parse_used_subcategories(content)

        assert len(result) == 3
        assert result.count("reports") == 2
        assert result.count("profile") == 1

    def test_parse_subcategories_case_sensitive_marker(self):
        """Test marker is case-sensitive (lowercase should not match)."""
        content = 'used_subcategories: ["reports"]'
        result = parse_used_subcategories(content)

        assert result == []

    def test_parse_subcategories_empty_string_input(self):
        """Test handles empty string input."""
        result = parse_used_subcategories("")

        assert result == []

    def test_parse_subcategories_with_hyphens(self):
        """Test parsing handles hyphenated subcategory names."""
        content = 'USED_SUBCATEGORIES: ["connect-account", "reports"]'
        result = parse_used_subcategories(content)

        assert len(result) == 2
        assert result[0] == "connect-account"
        assert result[1] == "reports"

    def test_parse_subcategories_mixed_with_sources(self):
        """Test parsing USED_SUBCATEGORIES when USED_SOURCES also present."""
        content = '''Analysis

USED_SOURCES: ["http://example.com"]
USED_SUBCATEGORIES: ["reports", "profile"]'''
        result = parse_used_subcategories(content)

        assert len(result) == 2
        assert result[0] == "reports"
        assert result[1] == "profile"
