"""Tests for title generation routes."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


class TestTitleGenerationRoutes:
    """Test suite for title generation API routes."""

    @pytest.mark.parametrize(
        "body,description",
        [
            (
                "This is a test content for generating title and summary. "
                "It contains multiple sentences to provide enough context.",
                "basic",
            ),
            ("a" * 10000, "max_valid_length"),
            ("Content with special chars: @#$%^&*()_+ and unicode: emojis 🎉", "special_characters"),
            ("Line 1: Intro\nLine 2: Body\nLine 3: End", "multiline"),
        ],
    )
    def test_generate_title_and_summary_success(self, client: TestClient, body, description):
        """Test successful title and summary generation validates API contract."""
        request_data = {"body": body}
        expected_result = {"title": "Generated Title", "summary": "Generated summary"}
        mock_generator = AsyncMock()
        mock_generator.generate_title_and_summary.return_value = expected_result

        with patch("app.api.routes_title_gen.title_generator", mock_generator):
            response = client.post("/title-gen/generate", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert "title" in data and isinstance(data["title"], str)
        assert "summary" in data and isinstance(data["summary"], str)
        mock_generator.generate_title_and_summary.assert_called_once_with(body)

    @pytest.mark.parametrize(
        "body,expected_status,expected_detail_fragment",
        [
            ("   ", 400, "Content body cannot be empty"),
            ("a" * 10001, 400, "Content body too large"),
            (None, 422, None),  # Missing body - validation error
        ],
    )
    def test_generate_title_and_summary_error_cases(
        self, client: TestClient, body, expected_status, expected_detail_fragment
    ):
        """Test title generation error scenarios."""
        request_data = {} if body is None else {"body": body}

        response = client.post("/title-gen/generate", json=request_data)

        assert response.status_code == expected_status
        data = response.json()
        assert "detail" in data
        if expected_detail_fragment:
            assert expected_detail_fragment in data["detail"]

    def test_generate_title_and_summary_service_error(self, client: TestClient):
        """Test title generation with service error."""
        request_data = {"body": "Test content"}
        mock_generator = AsyncMock()
        mock_generator.generate_title_and_summary.side_effect = Exception("LLM service error")

        with patch("app.api.routes_title_gen.title_generator", mock_generator):
            response = client.post("/title-gen/generate", json=request_data)

        assert response.status_code == 500
        data = response.json()
        assert "Internal server error generating title and summary" in data["detail"]
