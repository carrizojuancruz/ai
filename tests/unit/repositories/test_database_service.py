"""Tests for DatabaseService singleton."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.repositories.database_service import DatabaseService, get_database_service
from app.repositories.postgres.finance_repository import FinanceRepository
from app.repositories.postgres.user_repository import PostgresUserRepository


class TestDatabaseServiceSingleton:
    """Test DatabaseService singleton pattern."""

    def test_singleton_initialization(self, reset_database_service_globals):
        """Test that DatabaseService follows singleton pattern."""
        service1 = DatabaseService.get_instance()
        service2 = DatabaseService.get_instance()

        assert service1 is service2
        assert DatabaseService._instance is service1

    def test_direct_instantiation_raises_exception(self, reset_database_service_globals):
        """Test that direct instantiation after singleton creation raises exception."""
        DatabaseService.get_instance()

        with pytest.raises(Exception, match="DatabaseService is a singleton class"):
            DatabaseService()

    def test_get_database_service_returns_global_instance(self, reset_database_service_globals):
        """Test global get_database_service function."""
        global_instance = get_database_service()

        assert isinstance(global_instance, DatabaseService)
        assert global_instance is not None


class TestSessionFactory:
    """Test session factory initialization and management."""

    @pytest.mark.asyncio
    async def test_ensure_session_factory_initializes_once(self, reset_database_service_globals):
        """Test that session factory is initialized only once."""
        service = DatabaseService.get_instance()

        with patch('app.repositories.database_service.get_async_session_factory') as mock_factory:
            mock_factory.return_value = MagicMock()

            await service._ensure_session_factory()
            assert mock_factory.call_count == 1
            assert service._session_factory is not None

            await service._ensure_session_factory()
            assert mock_factory.call_count == 1

    @pytest.mark.asyncio
    async def test_ensure_session_factory_logs_initialization(self, reset_database_service_globals):
        """Test that session factory initialization is logged."""
        service = DatabaseService.get_instance()

        with (
            patch('app.repositories.database_service.get_async_session_factory') as mock_factory,
            patch('app.repositories.database_service.logger') as mock_logger,
        ):
            mock_factory.return_value = MagicMock()

            await service._ensure_session_factory()

            assert mock_logger.info.call_count == 2
            mock_logger.info.assert_any_call("Initializing database session factory")
            mock_logger.info.assert_any_call("Database session factory initialized successfully")


class TestGetSession:
    """Test get_session context manager."""

    @pytest.mark.asyncio
    async def test_get_session_initializes_factory(self, reset_database_service_globals):
        """Test that get_session initializes factory if needed."""
        service = DatabaseService.get_instance()
        mock_session = AsyncMock()

        with patch('app.repositories.database_service.get_async_session_factory') as mock_factory:
            mock_session_factory = MagicMock()
            mock_context_manager = AsyncMock()
            mock_context_manager.__aenter__.return_value = mock_session
            mock_context_manager.__aexit__.return_value = None
            mock_session_factory.return_value = mock_context_manager

            mock_factory.return_value = mock_session_factory

            async with service.get_session() as session:
                assert session is mock_session
                assert mock_factory.call_count == 1

    @pytest.mark.asyncio
    async def test_get_session_yields_session(self, reset_database_service_globals):
        """Test that get_session yields a session."""
        service = DatabaseService.get_instance()
        mock_session = AsyncMock()

        with patch('app.repositories.database_service.get_async_session_factory') as mock_factory:
            mock_session_factory = MagicMock()
            mock_context_manager = AsyncMock()
            mock_context_manager.__aenter__.return_value = mock_session
            mock_context_manager.__aexit__.return_value = None
            mock_session_factory.return_value = mock_context_manager

            mock_factory.return_value = mock_session_factory

            async with service.get_session() as session:
                assert session is mock_session

    @pytest.mark.asyncio
    async def test_get_session_logs_creation_and_closure(self, reset_database_service_globals):
        """Test that session creation and closure are logged."""
        service = DatabaseService.get_instance()
        mock_session = AsyncMock()

        with (
            patch('app.repositories.database_service.get_async_session_factory') as mock_factory,
            patch('app.repositories.database_service.logger') as mock_logger,
        ):
            mock_session_factory = MagicMock()
            mock_context_manager = AsyncMock()
            mock_context_manager.__aenter__.return_value = mock_session
            mock_context_manager.__aexit__.return_value = None
            mock_session_factory.return_value = mock_context_manager

            mock_factory.return_value = mock_session_factory

            async with service.get_session():
                pass

            assert mock_logger.debug.call_count >= 1
            mock_logger.debug.assert_any_call("Database session created")

    @pytest.mark.asyncio
    async def test_get_session_cleanup_on_exception(self, reset_database_service_globals):
        """Test that session is properly cleaned up even on exception."""
        service = DatabaseService.get_instance()
        mock_session = AsyncMock()

        with (
            patch('app.repositories.database_service.get_async_session_factory') as mock_factory,
            patch('app.repositories.database_service.logger') as mock_logger,
        ):
            mock_session_factory = MagicMock()
            mock_context_manager = AsyncMock()
            mock_context_manager.__aenter__.return_value = mock_session
            mock_context_manager.__aexit__.return_value = None
            mock_session_factory.return_value = mock_context_manager

            mock_factory.return_value = mock_session_factory

            with pytest.raises(ValueError):
                async with service.get_session():
                    raise ValueError("Test exception")

            mock_logger.debug.assert_any_call("Database session closed")


class TestRepositoryGetters:
    """Test repository getter methods."""

    def test_get_user_repository_returns_postgres_user_repository(
        self, reset_database_service_globals, mock_session
    ):
        """Test that get_user_repository returns PostgresUserRepository instance."""
        service = DatabaseService.get_instance()

        repo = service.get_user_repository(mock_session)

        assert isinstance(repo, PostgresUserRepository)
        assert repo.session is mock_session

    def test_repository_getters_create_new_instances(self, reset_database_service_globals, mock_session):
        """Test that repository getters create new instance for each call."""
        service = DatabaseService.get_instance()

        user_repo1 = service.get_user_repository(mock_session)
        user_repo2 = service.get_user_repository(mock_session)
        finance_repo1 = service.get_finance_repository(mock_session)
        finance_repo2 = service.get_finance_repository(mock_session)

        assert user_repo1 is not user_repo2
        assert user_repo1.session is mock_session
        assert user_repo2.session is mock_session

        assert finance_repo1 is not finance_repo2
        assert finance_repo1.session is mock_session
        assert finance_repo2.session is mock_session

    def test_get_finance_repository_returns_finance_repository(self, reset_database_service_globals, mock_session):
        """Test that get_finance_repository returns FinanceRepository instance."""
        service = DatabaseService.get_instance()

        repo = service.get_finance_repository(mock_session)

        assert isinstance(repo, FinanceRepository)
        assert repo.session is mock_session
