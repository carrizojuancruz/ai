"""Tests for the Goal Agent Models."""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.agents.supervisor.goal_agent.models import (
    AbsoluteAmount,
    AggregationMethod,
    Amount,
    Audit,
    DataSource,
    EvaluationConfig,
    EvaluationDirection,
    Frequency,
    Goal,
    GoalStatus,
    GoalStatusInfo,
    Progress,
    RecurrentFrequency,
    RoundingMethod,
)


class TestGoalStatusInfo:
    """Test cases for GoalStatusInfo model."""

    def test_goal_status_info_default(self):
        """Test GoalStatusInfo with default values."""
        # Act
        status = GoalStatusInfo()

        # Assert
        assert status.value == GoalStatus.PENDING

    def test_goal_status_info_with_value(self):
        """Test GoalStatusInfo with specific value."""
        # Act
        status = GoalStatusInfo(value=GoalStatus.IN_PROGRESS)

        # Assert
        assert status.value == GoalStatus.IN_PROGRESS


class TestAudit:
    """Test cases for Audit model."""

    def test_audit_creation(self):
        """Test Audit model creation."""
        # Arrange
        created_at = datetime.now()
        updated_at = datetime.now()

        # Act
        audit = Audit(created_at=created_at, updated_at=updated_at)

        # Assert
        assert audit.created_at == created_at
        assert audit.updated_at == updated_at

    def test_audit_optional_fields(self):
        """Test Audit model with optional fields."""
        # Act
        audit = Audit()

        # Assert
        assert audit.created_at is None
        assert audit.updated_at is None


class TestProgress:
    """Test cases for Progress model."""

    def test_progress_creation(self):
        """Test Progress model creation."""
        # Arrange
        current_value = Decimal("1500.50")
        percent_complete = Decimal("75.5")
        updated_at = datetime.now()

        # Act
        progress = Progress(
            current_value=current_value,
            percent_complete=percent_complete,
            updated_at=updated_at
        )

        # Assert
        assert progress.current_value == current_value
        assert progress.percent_complete == percent_complete
        assert progress.updated_at == updated_at

    def test_progress_validation_percent_range(self):
        """Test Progress validation for percent range."""
        # Act & Assert - Should not raise for valid percentage
        progress = Progress(percent_complete=Decimal("50"))
        assert progress.percent_complete == Decimal("50")

        # Act & Assert - Should raise for invalid percentage
        with pytest.raises(ValidationError):
            Progress(percent_complete=Decimal("150"))


class TestAbsoluteAmount:
    """Test cases for AbsoluteAmount model."""

    def test_absolute_amount_creation(self):
        """Test AbsoluteAmount model creation."""
        # Act
        amount = AbsoluteAmount(currency="USD", target=Decimal("5000"))

        # Assert
        assert amount.currency == "USD"
        assert amount.target == Decimal("5000")

    def test_absolute_amount_default_currency(self):
        """Test AbsoluteAmount with default currency."""
        # Act
        amount = AbsoluteAmount(target=Decimal("1000"))

        # Assert
        assert amount.currency == "USD"


class TestAmount:
    """Test cases for Amount model."""

    def test_amount_absolute(self):
        """Test Amount with absolute type."""
        # Arrange
        absolute_amount = AbsoluteAmount(currency="EUR", target=Decimal("2500"))

        # Act
        amount = Amount(type="absolute", absolute=absolute_amount)

        # Assert
        assert amount.type == "absolute"
        assert amount.absolute.currency == "EUR"
        assert amount.absolute.target == Decimal("2500")
        assert amount.percentage is None


class TestFrequency:
    """Test cases for Frequency model."""

    def test_frequency_recurrent(self):
        """Test Frequency with recurrent type."""
        # Arrange
        recurrent = RecurrentFrequency(
            unit="month",
            every=1,
            start_date="2024-01-01T00:00:00",
            end_date="2024-12-31T23:59:59"
        )

        # Act
        frequency = Frequency(type="recurrent", recurrent=recurrent)

        # Assert
        assert frequency.type == "recurrent"
        assert frequency.recurrent.unit == "month"
        assert frequency.recurrent.every == 1
        assert frequency.specific is None


class TestEvaluationConfig:
    """Test cases for EvaluationConfig model."""

    def test_evaluation_config_defaults(self):
        """Test EvaluationConfig with default values."""
        # Act
        config = EvaluationConfig()

        # Assert
        assert config.aggregation == AggregationMethod.SUM
        assert config.direction == EvaluationDirection.LESS_EQUAL
        assert config.rounding == RoundingMethod.NONE
        assert config.source == DataSource.MIXED
        assert config.affected_categories is None

    def test_evaluation_config_custom_values(self):
        """Test EvaluationConfig with custom values."""
        # Act
        config = EvaluationConfig(
            aggregation=AggregationMethod.AVERAGE,
            direction=EvaluationDirection.GREATER_EQUAL,
            source=DataSource.LINKED_ACCOUNTS,
            affected_categories=["food_drink", "entertainment"]
        )

        # Assert
        assert config.aggregation == AggregationMethod.AVERAGE
        assert config.direction == EvaluationDirection.GREATER_EQUAL
        assert config.source == DataSource.LINKED_ACCOUNTS
        assert config.affected_categories == ["food_drink", "entertainment"]


class TestGoal:
    """Test cases for Goal model."""

    def test_goal_creation_minimal(self):
        """Test Goal creation with minimal required fields."""
        # Arrange
        user_id = uuid4()
        goal_data = {
            "user_id": user_id,
            "goal": {"title": "Save for vacation"},
            "category": {"value": "saving"},
            "nature": {"value": "increase"},
            "frequency": {
                "type": "recurrent",
                "recurrent": {
                    "unit": "month",
                    "every": 1,
                    "start_date": "2024-01-01T00:00:00",
                    "end_date": "2024-12-31T23:59:59"
                }
            },
            "amount": {
                "type": "absolute",
                "absolute": {
                    "currency": "USD",
                    "target": 5000
                }
            }
        }

        # Act
        goal = Goal(**goal_data)

        # Assert
        assert goal.user_id == user_id
        assert goal.goal.title == "Save for vacation"
        assert goal.category.value == "saving"
        assert goal.nature.value == "increase"
        assert goal.status.value == GoalStatus.PENDING
        assert goal.version == 1

    def test_goal_validation_frequency_mismatch(self):
        """Test Goal validation for frequency type mismatch."""
        # Arrange
        user_id = uuid4()
        invalid_goal_data = {
            "user_id": user_id,
            "goal": {"title": "Test goal"},
            "category": {"value": "saving"},
            "nature": {"value": "increase"},
            "frequency": {
                "type": "recurrent"
                # Missing recurrent configuration
            },
            "amount": {
                "type": "absolute",
                "absolute": {
                    "currency": "USD",
                    "target": 5000
                }
            }
        }

        # Act & Assert
        with pytest.raises(TypeError) as exc_info:
            Goal(**invalid_goal_data)

        assert "argument 'line_errors'" in str(exc_info.value)

    def test_goal_validation_amount_mismatch(self):
        """Test Goal validation for amount type mismatch."""
        # Arrange
        user_id = uuid4()
        invalid_goal_data = {
            "user_id": user_id,
            "goal": {"title": "Test goal"},
            "category": {"value": "saving"},
            "nature": {"value": "increase"},
            "frequency": {
                "type": "recurrent",
                "recurrent": {
                    "unit": "month",
                    "every": 1,
                    "start_date": "2024-01-01T00:00:00",
                    "end_date": "2024-12-31T23:59:59"
                }
            },
            "amount": {
                "type": "absolute"
                # Missing absolute configuration
            }
        }

        # Act & Assert
        with pytest.raises(TypeError) as exc_info:
            Goal(**invalid_goal_data)

        assert "argument 'line_errors'" in str(exc_info.value)

    def test_goal_serialization(self):
        """Test Goal model serialization."""
        # Arrange
        user_id = uuid4()
        goal = Goal(
            user_id=user_id,
            goal={"title": "Test goal"},
            category={"value": "saving"},
            nature={"value": "increase"},
            frequency={
                "type": "recurrent",
                "recurrent": {
                    "unit": "month",
                    "every": 1,
                    "start_date": "2024-01-01T00:00:00",
                    "end_date": "2024-12-31T23:59:59"
                }
            },
            amount={
                "type": "absolute",
                "absolute": {
                    "currency": "USD",
                    "target": 5000
                }
            }
        )

        # Act
        json_str = goal.model_dump_json()
        data = goal.model_dump()

        # Assert
        assert isinstance(json_str, str)
        assert isinstance(data, dict)
        assert data["user_id"] == user_id  # UUID should remain as UUID object
        assert data["goal"]["title"] == "Test goal"
