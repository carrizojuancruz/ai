"""
Unit tests for app.services.nudges.strategies.goal_strategy module.

Tests cover:
- GoalNudgeStrategy initialization
- Properties (nudge_type, requires_fos_text)
- evaluate method with various goal states (completed, high_progress, pending, near_deadline)
- Priority selection among multiple goals
- Filtering logic (notifications disabled, no goals)
- Error handling
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.agents.supervisor.goal_agent.models import (
    AbsoluteAmount,
    Amount,
    Frequency,
    Goal,
    GoalBase,
    GoalCategoryInfo,
    GoalKind,
    GoalNatureInfo,
    GoalStatusInfo,
    Progress,
)
from app.services.nudges.strategies.goal_strategy import GoalNudgeStrategy


@pytest.fixture
def mock_db_service():
    """Fixture to mock database service."""
    with patch("app.services.nudges.strategies.goal_strategy.get_database_service") as mock_get:
        mock_service = MagicMock()
        mock_session = AsyncMock()
        mock_service.get_session.return_value.__aenter__.return_value = mock_session
        mock_service.get_session.return_value.__aexit__.return_value = None
        mock_get.return_value = mock_service
        yield mock_service, mock_session


@pytest.fixture
def mock_user_id():
    """Fixture for consistent user ID."""
    return uuid4()


@pytest.fixture
def sample_goal_completed(mock_user_id):
    """Fixture for a completed goal."""
    return Goal(
        goal_id=uuid4(),
        user_id=mock_user_id,
        goal=GoalBase(title="Save $10,000", description="Emergency fund"),
        category=GoalCategoryInfo(value="saving"),
        nature=GoalNatureInfo(value="increase"),
        frequency=Frequency(type="specific", specific={"date": datetime.now()}),
        amount=Amount(type="absolute", absolute=AbsoluteAmount(currency="USD", target=Decimal("10000.00"))),
        kind=GoalKind.FINANCIAL_PUNCTUAL,
        status=GoalStatusInfo(value="completed"),
        progress=Progress(
            current_value=Decimal("10000.00"), percent_complete=Decimal("100.00"), updated_at=datetime.now()
        ),
        evaluation={"affected_categories": ["INCOME", "TRANSFER_IN"]},
        notifications_enabled=True,
        end_date=datetime.now(),
        no_end_date=False,
    )


@pytest.fixture
def sample_goal_high_progress(mock_user_id):
    """Fixture for a goal with high progress (>=75%)."""
    return Goal(
        goal_id=uuid4(),
        user_id=mock_user_id,
        goal=GoalBase(title="Reduce spending by 20%", description="Cut expenses"),
        category=GoalCategoryInfo(value="spending"),
        nature=GoalNatureInfo(value="reduce"),
        frequency=Frequency(type="recurrent", recurrent={"unit": "month", "every": 1, "start_date": datetime.now()}),
        amount=Amount(type="percentage", percentage={"target_pct": Decimal("20.00"), "of": {"basis": "spending"}}),
        kind=GoalKind.FINANCIAL_HABIT,
        status=GoalStatusInfo(value="in_progress"),
        progress=Progress(
            current_value=Decimal("750.00"), percent_complete=Decimal("85.00"), updated_at=datetime.now()
        ),
        evaluation={"affected_categories": ["FOOD_AND_DRINK", "ENTERTAINMENT"]},
        notifications_enabled=True,
        end_date=datetime.now() + timedelta(days=30),
        no_end_date=False,
    )


@pytest.fixture
def sample_goal_pending(mock_user_id):
    """Fixture for a pending goal."""
    return Goal(
        goal_id=uuid4(),
        user_id=mock_user_id,
        goal=GoalBase(title="Start investing", description="Begin investment journey"),
        category=GoalCategoryInfo(value="investment"),
        nature=GoalNatureInfo(value="increase"),
        frequency=Frequency(type="recurrent", recurrent={"unit": "month", "every": 1, "start_date": datetime.now()}),
        amount=Amount(type="absolute", absolute=AbsoluteAmount(currency="USD", target=Decimal("5000.00"))),
        kind=GoalKind.FINANCIAL_HABIT,
        status=GoalStatusInfo(value="pending"),
        progress=Progress(current_value=Decimal("0.00"), percent_complete=Decimal("0.00"), updated_at=datetime.now()),
        evaluation={"affected_categories": ["TRANSFER_OUT"]},
        notifications_enabled=True,
        end_date=None,
        no_end_date=True,
    )


@pytest.fixture
def sample_goal_near_deadline(mock_user_id):
    """Fixture for a goal with deadline in exactly 7 days (no time component)."""
    now = datetime.now()
    # Create a date exactly 7 days in the future by setting to start of day
    deadline = (now + timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
    # Adjust so (deadline - now).days == 7
    deadline = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=7)

    return Goal(
        goal_id=uuid4(),
        user_id=mock_user_id,
        goal=GoalBase(title="Pay off credit card", description="Clear debt"),
        category=GoalCategoryInfo(value="debt"),
        nature=GoalNatureInfo(value="reduce"),
        frequency=Frequency(type="specific"),
        amount=Amount(type="absolute", absolute=AbsoluteAmount(currency="USD", target=Decimal("3000.00"))),
        kind=GoalKind.FINANCIAL_PUNCTUAL,
        status=GoalStatusInfo(value="in_progress"),
        progress=Progress(
            current_value=Decimal("1500.00"), percent_complete=Decimal("50.00"), updated_at=datetime.now()
        ),
        evaluation={"affected_categories": ["LOAN_PAYMENTS"]},
        notifications_enabled=True,
        end_date=deadline,
        no_end_date=False,
    )


class TestGoalNudgeStrategyInit:
    """Test GoalNudgeStrategy initialization."""

    def test_init_gets_database_service(self, mock_db_service):
        """Test initialization gets database service."""
        strategy = GoalNudgeStrategy()
        assert strategy.db_service is not None

    def test_init_sets_priority_map(self, mock_db_service):
        """Test initialization sets correct priority map."""
        strategy = GoalNudgeStrategy()
        assert strategy.priority_map == {
            "goal_completed": 5,
            "goal_near_deadline": 4,
            "goal_high_progress": 3,
            "goal_pending": 2,
        }

    def test_nudge_type_property(self, mock_db_service):
        """Test nudge_type property returns correct value."""
        strategy = GoalNudgeStrategy()
        assert strategy.nudge_type == "goal_based"

    def test_requires_fos_text_property(self, mock_db_service):
        """Test requires_fos_text property returns False."""
        strategy = GoalNudgeStrategy()
        assert strategy.requires_fos_text is False


class TestGoalNudgeStrategyEvaluateSuccess:
    """Test successful evaluate scenarios for different goal states."""

    @pytest.mark.asyncio
    async def test_evaluate_goal_completed_success(self, mock_db_service, mock_user_id, sample_goal_completed):
        """Test evaluate with completed goal returns correct NudgeCandidate."""
        mock_service, mock_session = mock_db_service

        with patch("app.services.nudges.strategies.goal_strategy.GoalsRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_goals_by_user.return_value = [sample_goal_completed]
            mock_repo_class.return_value = mock_repo

            strategy = GoalNudgeStrategy()
            result = await strategy.evaluate(mock_user_id, {})

            assert result is not None
            assert result.nudge_type == "goal_based"
            assert result.priority == 5
            assert result.user_id == mock_user_id
            assert "goal_completed" in result.metadata["nudge_id"]
            assert str(sample_goal_completed.goal_id) == result.metadata["goal_id"]
            assert result.metadata["status"] == "completed"
            assert result.metadata["percent_complete"] == 100.0
            assert result.metadata["goal_title"] == "Save $10,000"
            assert "🎉" in result.notification_text
            assert "completed" in result.notification_text.lower()
            assert "Save $10,000" in result.notification_text
            assert result.preview_text == "Goal completed!"

            mock_repo.get_goals_by_user.assert_called_once_with(mock_user_id, is_active=True)

    @pytest.mark.asyncio
    async def test_evaluate_goal_high_progress_success(self, mock_db_service, mock_user_id, sample_goal_high_progress):
        """Test evaluate with high progress goal (>=75%) returns correct NudgeCandidate."""
        mock_service, mock_session = mock_db_service

        with patch("app.services.nudges.strategies.goal_strategy.GoalsRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_goals_by_user.return_value = [sample_goal_high_progress]
            mock_repo_class.return_value = mock_repo

            strategy = GoalNudgeStrategy()
            result = await strategy.evaluate(mock_user_id, {})

            assert result is not None
            assert result.nudge_type == "goal_based"
            assert result.priority == 3
            assert result.metadata["nudge_id"] == "goal_high_progress"
            assert result.metadata["percent_complete"] == 85.0
            assert result.metadata["goal_title"] == "Reduce spending by 20%"
            assert "🚀" in result.notification_text
            assert "85%" in result.notification_text
            assert "almost there" in result.notification_text.lower()
            assert "85% complete" in result.preview_text

    @pytest.mark.asyncio
    async def test_evaluate_goal_pending_success(self, mock_db_service, mock_user_id, sample_goal_pending):
        """Test evaluate with pending goal returns correct NudgeCandidate."""
        mock_service, mock_session = mock_db_service

        with patch("app.services.nudges.strategies.goal_strategy.GoalsRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_goals_by_user.return_value = [sample_goal_pending]
            mock_repo_class.return_value = mock_repo

            strategy = GoalNudgeStrategy()
            result = await strategy.evaluate(mock_user_id, {})

            assert result is not None
            assert result.nudge_type == "goal_based"
            assert result.priority == 2
            assert result.metadata["nudge_id"] == "goal_pending"
            assert result.metadata["status"] == "pending"
            assert result.metadata["goal_title"] == "Start investing"
            assert "💪" in result.notification_text
            assert "Ready to start" in result.notification_text
            assert "Start investing" in result.notification_text
            assert result.preview_text == "Ready to start?"

    @pytest.mark.asyncio
    async def test_evaluate_goal_near_deadline_success(self, mock_db_service, mock_user_id, sample_goal_near_deadline):
        """Test evaluate with goal near deadline (7 days) returns correct NudgeCandidate."""
        mock_service, mock_session = mock_db_service

        # Mock datetime.now() to ensure consistent calculation
        fixed_now = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
        sample_goal_near_deadline.end_date = fixed_now + timedelta(days=7)

        with patch("app.services.nudges.strategies.goal_strategy.GoalsRepository") as mock_repo_class, patch(
            "app.services.nudges.strategies.goal_strategy.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = fixed_now
            mock_repo = AsyncMock()
            mock_repo.get_goals_by_user.return_value = [sample_goal_near_deadline]
            mock_repo_class.return_value = mock_repo

            strategy = GoalNudgeStrategy()
            result = await strategy.evaluate(mock_user_id, {})

            assert result is not None
            assert result.nudge_type == "goal_based"
            assert result.priority == 4
            assert result.metadata["nudge_id"] == "goal_near_deadline"
            assert result.metadata["goal_title"] == "Pay off credit card"
            assert "⏰" in result.notification_text
            assert "7 days" in result.notification_text
            assert "Pay off credit card" in result.notification_text
            assert result.preview_text == "Deadline approaching"


class TestGoalNudgeStrategyEvaluateFiltering:
    """Test filtering and edge cases in evaluate method."""

    @pytest.mark.asyncio
    async def test_evaluate_no_goals_returns_none(self, mock_db_service, mock_user_id):
        """Test evaluate returns None when user has no active goals."""
        mock_service, mock_session = mock_db_service

        with patch("app.services.nudges.strategies.goal_strategy.GoalsRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_goals_by_user.return_value = []
            mock_repo_class.return_value = mock_repo

            strategy = GoalNudgeStrategy()
            result = await strategy.evaluate(mock_user_id, {})

            assert result is None
            mock_repo.get_goals_by_user.assert_called_once_with(mock_user_id, is_active=True)

    @pytest.mark.asyncio
    async def test_evaluate_notifications_disabled_returns_none(
        self, mock_db_service, mock_user_id, sample_goal_completed
    ):
        """Test evaluate returns None when all goals have notifications disabled."""
        mock_service, mock_session = mock_db_service

        # Disable notifications
        sample_goal_completed.notifications_enabled = False

        with patch("app.services.nudges.strategies.goal_strategy.GoalsRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_goals_by_user.return_value = [sample_goal_completed]
            mock_repo_class.return_value = mock_repo

            strategy = GoalNudgeStrategy()
            result = await strategy.evaluate(mock_user_id, {})

            assert result is None

    @pytest.mark.asyncio
    async def test_evaluate_selects_highest_priority_goal(
        self,
        mock_db_service,
        mock_user_id,
        sample_goal_completed,
        sample_goal_high_progress,
        sample_goal_pending,
        sample_goal_near_deadline,
    ):
        """Test evaluate selects highest priority goal when multiple goals are eligible."""
        mock_service, mock_session = mock_db_service

        # All goals are eligible, but completed should win (priority 5)
        goals = [
            sample_goal_pending,  # priority 2
            sample_goal_high_progress,  # priority 3
            sample_goal_near_deadline,  # priority 4
            sample_goal_completed,  # priority 5 - should win
        ]

        with patch("app.services.nudges.strategies.goal_strategy.GoalsRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_goals_by_user.return_value = goals
            mock_repo_class.return_value = mock_repo

            strategy = GoalNudgeStrategy()
            result = await strategy.evaluate(mock_user_id, {})

            assert result is not None
            assert result.priority == 5
            assert result.metadata["nudge_id"] == "goal_completed"
            assert result.metadata["goal_id"] == str(sample_goal_completed.goal_id)

    @pytest.mark.asyncio
    async def test_evaluate_completed_without_end_date_returns_none(
        self, mock_db_service, mock_user_id, sample_goal_completed
    ):
        """Test evaluate returns None for completed goal without end_date."""
        mock_service, mock_session = mock_db_service

        # Make goal completed but with no_end_date=True
        sample_goal_completed.no_end_date = True

        with patch("app.services.nudges.strategies.goal_strategy.GoalsRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_goals_by_user.return_value = [sample_goal_completed]
            mock_repo_class.return_value = mock_repo

            strategy = GoalNudgeStrategy()
            result = await strategy.evaluate(mock_user_id, {})

            assert result is None

    @pytest.mark.asyncio
    async def test_evaluate_in_progress_below_75_percent_not_triggered(
        self, mock_db_service, mock_user_id, sample_goal_high_progress
    ):
        """Test evaluate returns None for in_progress goal below 75% (unless other conditions met)."""
        mock_service, mock_session = mock_db_service

        # Set progress below 75% and deadline far away
        sample_goal_high_progress.progress.percent_complete = Decimal("50.00")
        sample_goal_high_progress.end_date = datetime.now() + timedelta(days=30)

        with patch("app.services.nudges.strategies.goal_strategy.GoalsRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_goals_by_user.return_value = [sample_goal_high_progress]
            mock_repo_class.return_value = mock_repo

            strategy = GoalNudgeStrategy()
            result = await strategy.evaluate(mock_user_id, {})

            assert result is None


class TestGoalNudgeStrategyErrorHandling:
    """Test error handling in evaluate method."""

    @pytest.mark.asyncio
    async def test_evaluate_database_error_returns_none(self, mock_db_service, mock_user_id):
        """Test evaluate returns None and logs error when database query fails."""
        mock_service, mock_session = mock_db_service

        with patch("app.services.nudges.strategies.goal_strategy.GoalsRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_goals_by_user.side_effect = Exception("Database connection failed")
            mock_repo_class.return_value = mock_repo

            strategy = GoalNudgeStrategy()

            with patch("app.services.nudges.strategies.goal_strategy.logger") as mock_logger:
                result = await strategy.evaluate(mock_user_id, {})

                assert result is None
                mock_logger.error.assert_called_once()
                error_call_args = mock_logger.error.call_args[0][0]
                assert "goal_strategy.evaluation_failed" in error_call_args
                assert str(mock_user_id) in error_call_args

    @pytest.mark.asyncio
    async def test_evaluate_repository_instantiation_error_returns_none(self, mock_db_service, mock_user_id):
        """Test evaluate handles repository instantiation errors gracefully."""
        mock_service, mock_session = mock_db_service

        with patch(
            "app.services.nudges.strategies.goal_strategy.GoalsRepository",
            side_effect=Exception("Repository init failed"),
        ):
            strategy = GoalNudgeStrategy()

            with patch("app.services.nudges.strategies.goal_strategy.logger") as mock_logger:
                result = await strategy.evaluate(mock_user_id, {})

                assert result is None
                mock_logger.error.assert_called_once()


class TestGoalNudgeStrategyGetPriority:
    """Test get_priority method."""

    def test_get_priority_with_valid_nudge_id(self, mock_db_service):
        """Test get_priority returns correct priority for valid nudge_id."""
        strategy = GoalNudgeStrategy()

        assert strategy.get_priority({"nudge_id": "goal_completed"}) == 5
        assert strategy.get_priority({"nudge_id": "goal_near_deadline"}) == 4
        assert strategy.get_priority({"nudge_id": "goal_high_progress"}) == 3
        assert strategy.get_priority({"nudge_id": "goal_pending"}) == 2

    def test_get_priority_with_invalid_nudge_id(self, mock_db_service):
        """Test get_priority returns default priority for invalid nudge_id."""
        strategy = GoalNudgeStrategy()

        assert strategy.get_priority({"nudge_id": "invalid_nudge"}) == 2

    def test_get_priority_with_missing_nudge_id(self, mock_db_service):
        """Test get_priority returns default priority when nudge_id is missing."""
        strategy = GoalNudgeStrategy()

        assert strategy.get_priority({}) == 2
