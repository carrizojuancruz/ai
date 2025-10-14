"""Tests for the Goal Agent Utils."""

from app.agents.supervisor.goal_agent.utils import preprocess_goal_data


class TestPreprocessGoalData:
    """Test cases for preprocess_goal_data function."""

    def test_preprocess_goal_data_basic_structure(self):
        """Test basic preprocessing of goal data."""
        # Arrange
        input_data = {
            "title": "Save for vacation",
            "category": "saving",
            "nature": "increase",
            "amount": 5000
        }

        # Act
        result = preprocess_goal_data(input_data, "test-user-123")

        # Assert
        assert result["user_id"] == "test-user-123"
        assert result["goal"]["title"] == "Save for vacation"
        assert result["category"]["value"] == "saving"
        assert result["nature"]["value"] == "increase"
        assert result["amount"] == 5000

    def test_preprocess_goal_data_with_existing_goal_structure(self):
        """Test preprocessing when goal structure already exists."""
        # Arrange
        input_data = {
            "goal": {"title": "Existing goal"},
            "category": {"value": "saving"},
            "nature": {"value": "increase"}
        }

        # Act
        result = preprocess_goal_data(input_data, "test-user-123")

        # Assert
        assert result["goal"]["title"] == "Existing goal"
        assert result["category"]["value"] == "saving"
        assert result["nature"]["value"] == "increase"

    def test_preprocess_goal_data_missing_goal_title(self):
        """Test preprocessing when goal title is missing."""
        # Arrange
        input_data = {
            "category": "saving",
            "nature": "increase"
        }

        # Act
        result = preprocess_goal_data(input_data, "test-user-123")

        # Assert
        assert result["goal"]["title"] == "Enter goal title"  # Default title

    def test_preprocess_goal_data_string_category(self):
        """Test preprocessing with string category (should convert to dict)."""
        # Arrange
        input_data = {
            "goal": {"title": "Test goal"},
            "category": "saving",  # String instead of dict
            "nature": "increase"
        }

        # Act
        result = preprocess_goal_data(input_data, "test-user-123")

        # Assert
        assert result["category"]["value"] == "saving"

    def test_preprocess_goal_data_string_nature(self):
        """Test preprocessing with string nature (should convert to dict)."""
        # Arrange
        input_data = {
            "goal": {"title": "Test goal"},
            "category": "saving",
            "nature": "increase"  # String instead of dict
        }

        # Act
        result = preprocess_goal_data(input_data, "test-user-123")

        # Assert
        assert result["nature"]["value"] == "increase"

    def test_preprocess_goal_data_default_frequency(self):
        """Test that default frequency is set when missing."""
        # Arrange
        input_data = {
            "goal": {"title": "Test goal"},
            "category": "saving",
            "nature": "increase"
        }

        # Act
        result = preprocess_goal_data(input_data, "test-user-123")

        # Assert
        assert result["frequency"]["type"] == "recurrent"
        assert result["frequency"]["recurrent"]["unit"] == "month"
        assert result["frequency"]["recurrent"]["every"] == 1

    def test_preprocess_goal_data_default_amount(self):
        """Test that default amount is set when missing."""
        # Arrange
        input_data = {
            "goal": {"title": "Test goal"},
            "category": "saving",
            "nature": "increase"
        }

        # Act
        result = preprocess_goal_data(input_data, "test-user-123")

        # Assert
        assert result["amount"]["type"] == "absolute"
        assert result["amount"]["absolute"]["currency"] == "USD"
        assert result["amount"]["absolute"]["target"] == 1000  # Default target

    def test_preprocess_goal_data_pydantic_model(self):
        """Test preprocessing with Pydantic model input."""
        # Arrange
        class MockModel:
            def model_dump(self):
                return {
                    "goal": {"title": "Model goal"},
                    "category": "saving",
                    "nature": "increase"
                }

        input_data = MockModel()

        # Act
        result = preprocess_goal_data(input_data, "test-user-123")

        # Assert
        assert result["goal"]["title"] == "Model goal"
        assert result["category"]["value"] == "saving"

    def test_preprocess_goal_data_amount_conversion(self):
        """Test amount preprocessing with various formats."""
        # Arrange
        input_data = {
            "goal": {"title": "Test goal"},
            "category": "saving",
            "nature": "increase",
            "amount": {
                "target": 2500  # Direct target value
            }
        }

        # Act
        result = preprocess_goal_data(input_data, "test-user-123")

        # Assert
        assert result["amount"]["type"] == "absolute"
        assert result["amount"]["absolute"]["target"] == 2500
        assert result["amount"]["absolute"]["currency"] == "USD"
