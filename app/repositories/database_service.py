"""Database service for managing PostgreSQL connections and repositories.

This service provides a centralized way to manage database connections and repository instances,
following the singleton pattern used throughout the application.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session_factory
from app.repositories.interfaces.nudge_repository import NudgeRepository
from app.repositories.interfaces.user_repository import UserRepository
from app.repositories.postgres.finance_repository import FinanceRepository
from app.repositories.postgres.nudge_repository import PostgresNudgeRepository
from app.repositories.postgres.user_repository import PostgresUserRepository

logger = logging.getLogger(__name__)


class DatabaseService:
    """Singleton service for managing database connections and repositories."""

    _instance: Optional['DatabaseService'] = None
    _session_factory = None
    _user_repository: Optional[PostgresUserRepository] = None
    _finance_repository: Optional[FinanceRepository] = None

    def __init__(self):
        if DatabaseService._instance is not None:
            raise Exception("DatabaseService is a singleton class")
        DatabaseService._instance = self

    @classmethod
    def get_instance(cls) -> 'DatabaseService':
        """Get singleton instance of DatabaseService."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def _ensure_session_factory(self):
        """Ensure session factory is initialized."""
        if self._session_factory is None:
            logger.info("Initializing database session factory")
            self._session_factory = get_async_session_factory()
            logger.info("Database session factory initialized successfully")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session with automatic cleanup."""
        await self._ensure_session_factory()
        async with self._session_factory() as session:
            logger.debug("Database session created")
            try:
                yield session
            finally:
                logger.debug("Database session closed")

    def get_user_repository(self, session: AsyncSession) -> UserRepository:
        """Get user repository instance with the provided session."""
        return PostgresUserRepository(session)

    def get_finance_repository(self, session: AsyncSession) -> FinanceRepository:
        """Get finance repository instance with the provided session."""
        return FinanceRepository(session)

    def get_nudge_repository(self, session: AsyncSession) -> NudgeRepository:
        """Get nudge repository instance with the provided session."""
        return PostgresNudgeRepository(session)


# Global instance
_database_service = DatabaseService.get_instance()


def get_database_service() -> DatabaseService:
    """Get the global database service instance."""
    return _database_service
