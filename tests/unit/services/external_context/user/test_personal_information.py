"""Unit tests for PersonalInformationService.

Tests the formatting and aggregation of personal information from external sources.
Follows AAA pattern (Arrange-Act-Assert) and ensures deterministic, fast unit tests.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.external_context.user.personal_information import PersonalInformationService


@pytest.fixture
def service():
    """Fixture providing a PersonalInformationService instance."""
    return PersonalInformationService()


@pytest.fixture
def mock_http_client():
    """Mock FOSHttpClient for testing without external dependencies."""
    with patch('app.services.external_context.user.personal_information.FOSHttpClient') as mock:
        yield mock


class TestGetAllPersonalInfo:
    """Test cases for get_all_personal_info method."""

    @pytest.mark.asyncio
    async def test_success_with_all_data(self, service, mock_http_client):
        """Test successful fetch with all data sources returning valid data."""
        # Arrange
        mock_client_instance = AsyncMock()
        mock_http_client.return_value = mock_client_instance
        service.http_client = mock_client_instance

        mock_client_instance.get.side_effect = [
            {"interaction_style": "friendly", "topics_to_avoid": ["politics", "religion"]},
            {"topics": ["Spanish", "Finance"]},
            {"coverage_description": "Full coverage", "pays_for_self": True},
            {"financial_goals": ["Save for house", "Build emergency fund"]}
        ]

        # Act
        result = await service.get_all_personal_info("user_123")

        # Assert
        assert result is not None
        assert "friendly" in result
        assert "politics, religion" in result
        assert "Spanish, Finance" in result
        assert "Full coverage" in result
        assert "they pay for it themselves" in result
        assert "Save for house, Build emergency fund" in result

    @pytest.mark.asyncio
    async def test_partial_failure_continues_processing(self, service, mock_http_client):
        """Test that partial failures don't stop processing other sources."""
        # Arrange
        mock_client_instance = AsyncMock()
        mock_http_client.return_value = mock_client_instance
        service.http_client = mock_client_instance

        mock_client_instance.get.side_effect = [
            Exception("Network error"),
            {"topics": ["Spanish"]},
            {"coverage_description": "Basic", "pays_for_self": False},
            {"financial_goals": ["Retirement"]}
        ]

        # Act
        result = await service.get_all_personal_info("user_123")

        # Assert
        assert result is not None
        assert "Spanish" in result
        assert "Basic" in result
        assert "it's covered by someone else" in result
        assert "Retirement" in result

    @pytest.mark.asyncio
    async def test_all_sources_return_none(self, service, mock_http_client):
        """Test behavior when all sources return None."""
        # Arrange
        mock_client_instance = AsyncMock()
        mock_http_client.return_value = mock_client_instance
        service.http_client = mock_client_instance

        mock_client_instance.get.side_effect = [None, None, None, None]

        # Act
        result = await service.get_all_personal_info("user_123")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_all_sources_raise_exceptions(self, service, mock_http_client):
        """Test behavior when all sources fail with exceptions."""
        # Arrange
        mock_client_instance = AsyncMock()
        mock_http_client.return_value = mock_client_instance
        service.http_client = mock_client_instance

        mock_client_instance.get.side_effect = [
            Exception("Error 1"),
            Exception("Error 2"),
            Exception("Error 3"),
            Exception("Error 4")
        ]

        # Act
        result = await service.get_all_personal_info("user_123")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_data_structures(self, service, mock_http_client):
        """Test handling of empty but valid data structures."""
        # Arrange
        mock_client_instance = AsyncMock()
        mock_http_client.return_value = mock_client_instance
        service.http_client = mock_client_instance

        mock_client_instance.get.side_effect = [
            {"interaction_style": "casual", "topics_to_avoid": []},
            {"topics": []},
            {},
            {"financial_goals": []}
        ]

        # Act
        result = await service.get_all_personal_info("user_123")

        # Assert
        assert result is not None
        assert "casual" in result
        assert "none specified" in result

    @pytest.mark.asyncio
    async def test_correct_endpoints_called(self, service, mock_http_client):
        """Test that correct API endpoints are called with proper user_id."""
        # Arrange
        mock_client_instance = AsyncMock()
        mock_http_client.return_value = mock_client_instance
        service.http_client = mock_client_instance

        mock_client_instance.get.return_value = {}
        user_id = "test_user_456"

        # Act
        await service.get_all_personal_info(user_id)

        # Assert
        calls = mock_client_instance.get.call_args_list
        assert len(calls) == 5

        expected_endpoints = [
            f"/internal/users/profile/vera-approach/{user_id}",
            f"/internal/users/profile/learning-topics/{user_id}",
            f"/internal/users/profile/health-insurance/{user_id}",
            f"/internal/users/profile/financial-goals/{user_id}",
            f"/internal/users/profile/housing-info/{user_id}"
        ]

        actual_endpoints = [call[0][0] for call in calls]
        assert sorted(actual_endpoints) == sorted(expected_endpoints)


class TestFormatVeraApproach:
    """Test cases for _format_vera_approach method."""

    def test_format_with_complete_data(self, service):
        """Test formatting with all vera approach fields present."""
        # Arrange
        data = {
            "interaction_style": "professional",
            "topics_to_avoid": ["health", "family"]
        }

        # Act
        result = service._format_vera_approach(data)

        # Assert
        assert "professional" in result
        assert "health, family" in result
        assert "interaction style" in result.lower()

    def test_format_with_empty_topics_list(self, service):
        """Test formatting when topics_to_avoid is empty."""
        # Arrange
        data = {
            "interaction_style": "casual",
            "topics_to_avoid": []
        }

        # Act
        result = service._format_vera_approach(data)

        # Assert
        assert "casual" in result
        assert "none specified" in result

    def test_format_with_none_data(self, service):
        """Test formatting when data is None."""
        # Act
        result = service._format_vera_approach(None)

        # Assert
        assert result == ""

    def test_format_with_empty_dict(self, service):
        """Test formatting when data is empty dictionary."""
        # Act
        result = service._format_vera_approach({})

        # Assert
        assert result == ""

    def test_format_with_missing_fields(self, service):
        """Test formatting when required fields are missing."""
        # Arrange
        data = {"interaction_style": "friendly"}

        # Act
        result = service._format_vera_approach(data)

        # Assert
        assert "friendly" in result


class TestFormatLearningTopics:
    """Test cases for _format_learning_topics method."""

    def test_format_with_multiple_topics(self, service):
        """Test formatting with multiple learning topics."""
        # Arrange
        data = {"topics": ["Python", "Machine Learning", "Finance"]}

        # Act
        result = service._format_learning_topics(data)

        # Assert
        assert "Python, Machine Learning, Finance" in result
        assert "learning topics" in result.lower()

    def test_format_with_single_topic(self, service):
        """Test formatting with single learning topic."""
        # Arrange
        data = {"topics": ["Spanish"]}

        # Act
        result = service._format_learning_topics(data)

        # Assert
        assert "Spanish" in result

    def test_format_with_empty_topics(self, service):
        """Test formatting when topics list is empty."""
        # Arrange
        data = {"topics": []}

        # Act
        result = service._format_learning_topics(data)

        # Assert
        assert "none specified" in result

    def test_format_with_none_data(self, service):
        """Test formatting when data is None."""
        # Act
        result = service._format_learning_topics(None)

        # Assert
        assert result == ""


class TestFormatHealthInsurance:
    """Test cases for _format_health_insurance method."""

    def test_format_pays_for_self_true(self, service):
        """Test formatting when user pays for their own insurance."""
        # Arrange
        data = {
            "coverage_description": "Premium plan with dental",
            "pays_for_self": True
        }

        # Act
        result = service._format_health_insurance(data)

        # Assert
        assert "Premium plan with dental" in result
        assert "they pay for it themselves" in result

    def test_format_pays_for_self_false(self, service):
        """Test formatting when insurance is covered by someone else."""
        # Arrange
        data = {
            "coverage_description": "Basic plan",
            "pays_for_self": False
        }

        # Act
        result = service._format_health_insurance(data)

        # Assert
        assert "Basic plan" in result
        assert "it's covered by someone else" in result

    def test_format_with_none_data(self, service):
        """Test formatting when data is None."""
        # Act
        result = service._format_health_insurance(None)

        # Assert
        assert result == ""

    def test_format_with_empty_dict(self, service):
        """Test formatting when data is empty dictionary."""
        # Act
        result = service._format_health_insurance({})

        # Assert
        assert result == ""

    def test_format_with_missing_coverage_description(self, service):
        """Test formatting when coverage_description is missing."""
        # Arrange
        data = {"pays_for_self": True}

        # Act
        result = service._format_health_insurance(data)

        # Assert
        assert "unknown" in result


class TestFormatFinancialGoals:
    """Test cases for _format_financial_goals method."""

    def test_format_with_multiple_goals(self, service):
        """Test formatting with multiple financial goals."""
        # Arrange
        data = {"financial_goals": ["Buy a house", "Start a business", "Save for retirement"]}

        # Act
        result = service._format_financial_goals(data)

        # Assert
        assert "Buy a house, Start a business, Save for retirement" in result
        assert "financial goals" in result.lower()

    def test_format_with_single_goal(self, service):
        """Test formatting with single financial goal."""
        # Arrange
        data = {"financial_goals": ["Build emergency fund"]}

        # Act
        result = service._format_financial_goals(data)

        # Assert
        assert "Build emergency fund" in result

    def test_format_with_empty_goals(self, service):
        """Test formatting when financial_goals list is empty."""
        # Arrange
        data = {"financial_goals": []}

        # Act
        result = service._format_financial_goals(data)

        # Assert
        assert "none specified" in result

    def test_format_with_none_data(self, service):
        """Test formatting when data is None."""
        # Act
        result = service._format_health_insurance(None)

        # Assert
        assert result == ""


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_mixed_success_and_failure(self, service, mock_http_client):
        """Test with alternating success and failure responses."""
        # Arrange
        mock_client_instance = AsyncMock()
        mock_http_client.return_value = mock_client_instance
        service.http_client = mock_client_instance

        mock_client_instance.get.side_effect = [
            {"interaction_style": "professional", "topics_to_avoid": []},
            Exception("API timeout"),
            {"coverage_description": "Full", "pays_for_self": True},
            Exception("Service unavailable")
        ]

        # Act
        result = await service.get_all_personal_info("user_999")

        # Assert
        assert result is not None
        assert "professional" in result
        assert "Full" in result

    @pytest.mark.asyncio
    async def test_special_characters_in_data(self, service, mock_http_client):
        """Test handling of special characters in returned data."""
        # Arrange
        mock_client_instance = AsyncMock()
        mock_http_client.return_value = mock_client_instance
        service.http_client = mock_client_instance

        mock_client_instance.get.side_effect = [
            {"interaction_style": "friendly & casual", "topics_to_avoid": ["politics", "religion & spirituality"]},
            {"topics": ["C++", "Node.js"]},
            {"coverage_description": "Plan: Premium (Tier 1)", "pays_for_self": True},
            {"financial_goals": ["Save $50,000", "Invest 20%"]}
        ]

        # Act
        result = await service.get_all_personal_info("user_special")

        # Assert
        assert result is not None
        assert "friendly & casual" in result
        assert "C++, Node.js" in result
        assert "$50,000" in result

    @pytest.mark.asyncio
    async def test_empty_user_id(self, service, mock_http_client):
        """Test behavior with empty user_id."""
        # Arrange
        mock_client_instance = AsyncMock()
        mock_http_client.return_value = mock_client_instance
        service.http_client = mock_client_instance
        mock_client_instance.get.return_value = {}

        # Act
        await service.get_all_personal_info("")

        # Assert - Should still make API calls (validation is API's responsibility)
        assert mock_client_instance.get.call_count == 5
