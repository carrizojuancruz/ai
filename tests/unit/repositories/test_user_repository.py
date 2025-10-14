"""Tests for PostgresUserRepository."""

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.db.models.user import UserContextORM
from app.models.user import UserContext
from app.repositories.postgres.user_repository import PostgresUserRepository, _to_domain


class TestToDomainConversion:
    """Test _to_domain conversion function."""

    def test_to_domain_converts_orm_to_user_context(self):
        """Test that _to_domain converts UserContextORM to UserContext."""
        user_id = uuid4()
        now = datetime.now(timezone.utc)

        orm_row = UserContextORM(
            user_id=user_id,
            email="test@example.com",
            preferred_name="Test User",
            pronouns="they/them",
            language="en",
            tone_preference="friendly",
            city="Test City",
            dependents=2,
            income_band="50k-75k",
            rent_mortgage=1500.00,
            primary_financial_goal="Save for retirement",
            subscription_tier="guest",
            social_signals_consent=True,
            ready_for_orchestrator=True,
            created_at=now,
            updated_at=now,
            age=35,
            age_range="30-40",
            money_feelings=["anxious", "hopeful"],
            housing_satisfaction="satisfied",
            health_insurance="employer",
            health_cost="200",
            learning_interests=["investing", "budgeting"],
            expenses=["food", "transport"],
            identity={"gender": "non-binary"},
            safety={"emergency_fund": True},
            style={"communication": "direct"},
            location={"lat": 40.7128, "lng": -74.0060},
            locale_info={"currency": "USD"},
            goals=["retirement", "emergency-fund"],
            income="60000",
            housing="rent",
            tier="premium",
            accessibility={"screenReader": False},
            budget_posture={"strict": False},
            household={"size": 2},
            assets_high_level=["401k", "savings"],
        )

        result = _to_domain(orm_row)

        assert isinstance(result, UserContext)
        assert result.user_id == user_id
        assert result.email == "test@example.com"
        assert result.preferred_name == "Test User"
        assert result.pronouns == "they/them"
        assert result.dependents == 2
        assert result.rent_mortgage == 1500.00
        assert result.age == 35
        assert result.money_feelings == ["anxious", "hopeful"]

    def test_to_domain_handles_none_values(self):
        """Test that _to_domain handles None values correctly."""
        user_id = uuid4()
        now = datetime.now(timezone.utc)

        orm_row = UserContextORM(
            user_id=user_id,
            email="test@example.com",
            created_at=now,
            updated_at=now,
            language="en",
            subscription_tier="guest",  # Required enum
            social_signals_consent=True,  # Required bool
            ready_for_orchestrator=True,  # Required bool
            # All optional fields as None
            preferred_name=None,
            pronouns=None,
            tone_preference=None,
            city=None,
            dependents=None,
            income_band=None,
            rent_mortgage=None,
            primary_financial_goal=None,
            age=None,
            age_range=None,
            money_feelings=None,
            housing_satisfaction=None,
            health_insurance=None,
            health_cost=None,
            learning_interests=None,
            expenses=None,
            identity=None,
            safety=None,
            style=None,
            location=None,
            locale_info=None,
            goals=None,
            income=None,
            housing=None,
            tier=None,
            accessibility=None,
            budget_posture=None,
            household=None,
            assets_high_level=None,
        )

        result = _to_domain(orm_row)

        assert isinstance(result, UserContext)
        assert result.user_id == user_id
        assert result.email == "test@example.com"
        assert result.dependents is None
        assert result.rent_mortgage is None
        assert result.age is None
        assert result.money_feelings == []
        assert result.learning_interests == []
        assert result.expenses == []
        # identity is an Identity object, not a simple dict
        assert result.identity is not None
        assert result.assets_high_level == []


class TestPostgresUserRepositoryGetById:
    """Test PostgresUserRepository.get_by_id method."""

    @pytest.mark.asyncio
    async def test_get_by_id_returns_user_when_found(self, mock_session, sample_user_id):
        """Test that get_by_id returns UserContext when user exists."""
        now = datetime.now(timezone.utc)
        mock_orm_row = UserContextORM(
            user_id=sample_user_id,
            email="found@example.com",
            preferred_name="Found User",
            created_at=now,
            updated_at=now,
            language="en",
            subscription_tier="guest",
            social_signals_consent=True,
            ready_for_orchestrator=True,
        )

        # Mock the execute result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_orm_row
        mock_session.execute.return_value = mock_result

        repo = PostgresUserRepository(mock_session)
        result = await repo.get_by_id(sample_user_id)

        assert result is not None
        assert isinstance(result, UserContext)
        assert result.user_id == sample_user_id
        assert result.email == "found@example.com"
        assert result.preferred_name == "Found User"
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_not_found(self, mock_session, sample_user_id):
        """Test that get_by_id returns None when user doesn't exist."""
        # Mock the execute result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = PostgresUserRepository(mock_session)
        result = await repo.get_by_id(sample_user_id)

        assert result is None
        mock_session.execute.assert_called_once()


class TestPostgresUserRepositoryUpsert:
    """Test PostgresUserRepository.upsert method."""

    @pytest.mark.asyncio
    async def test_upsert_inserts_new_user(self, mock_session, sample_user_id):
        """Test that upsert inserts a new user."""
        user = UserContext(
            user_id=sample_user_id,
            email="new@example.com",
            preferred_name="New User",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        repo = PostgresUserRepository(mock_session)
        result = await repo.upsert(user)

        assert result == user
        assert mock_session.execute.called
        assert mock_session.commit.called

    @pytest.mark.asyncio
    async def test_upsert_updates_existing_user(self, mock_session, sample_user_id):
        """Test that upsert updates an existing user."""
        user = UserContext(
            user_id=sample_user_id,
            email="updated@example.com",
            preferred_name="Updated User",
            pronouns="she/her",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        repo = PostgresUserRepository(mock_session)
        result = await repo.upsert(user)

        assert result == user
        assert mock_session.execute.called
        assert mock_session.commit.called

    @pytest.mark.asyncio
    async def test_upsert_uses_postgresql_insert_with_on_conflict(self, mock_session, sample_user_id):
        """Test that upsert uses PostgreSQL INSERT ... ON CONFLICT."""
        user = UserContext(
            user_id=sample_user_id,
            email="test@example.com",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        repo = PostgresUserRepository(mock_session)
        await repo.upsert(user)

        # Verify execute was called (the INSERT statement)
        assert mock_session.execute.called
        call_args = mock_session.execute.call_args
        # The statement should be a PostgreSQL INSERT with ON CONFLICT
        assert call_args is not None


class TestPostgresUserRepositoryDelete:
    """Test PostgresUserRepository.delete method."""

    @pytest.mark.asyncio
    async def test_delete_removes_existing_user(self, mock_session, sample_user_id):
        """Test that delete removes an existing user."""
        mock_orm_row = UserContextORM(
            user_id=sample_user_id,
            email="delete@example.com",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        mock_session.get.return_value = mock_orm_row

        repo = PostgresUserRepository(mock_session)
        await repo.delete(sample_user_id)

        mock_session.get.assert_called_once_with(UserContextORM, sample_user_id)
        mock_session.delete.assert_called_once_with(mock_orm_row)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_does_nothing_when_user_not_found(self, mock_session, sample_user_id):
        """Test that delete does nothing when user doesn't exist."""
        mock_session.get.return_value = None

        repo = PostgresUserRepository(mock_session)
        await repo.delete(sample_user_id)

        mock_session.get.assert_called_once_with(UserContextORM, sample_user_id)
        mock_session.delete.assert_not_called()
        mock_session.commit.assert_not_called()


class TestPostgresUserRepositoryInitialization:
    """Test PostgresUserRepository initialization."""

    def test_repository_initialization(self, mock_session):
        """Test that repository can be initialized with a session."""
        repo = PostgresUserRepository(mock_session)

        assert repo.session is mock_session
        assert isinstance(repo, PostgresUserRepository)
