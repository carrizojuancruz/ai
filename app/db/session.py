from __future__ import annotations

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import config

logger = logging.getLogger(__name__)

DATABASE_URL = config.get_database_url()

# Lazy-loaded database components
_engine = None
_async_session_factory = None


def _get_engine():
    """Lazy-load database engine to avoid connection attempts at startup."""
    global _engine
    if _engine is None:
        try:
            _engine = create_async_engine(DATABASE_URL, echo=False, future=True)
            logger.info("Database engine created successfully")
        except Exception as e:
            logger.warning(f"Database connection failed (this is expected in production): {e}")
            raise
    return _engine


def _get_session_factory():
    """Lazy-load session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            _get_engine(),
            expire_on_commit=False,
            class_=AsyncSession
        )
    return _async_session_factory


def get_engine():
    """Get database engine (lazy-loaded)."""
    return _get_engine()


def get_async_session_factory():
    """Get async session factory (lazy-loaded)."""
    return _get_session_factory()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session. Will fail gracefully if database is not available."""
    try:
        factory = _get_session_factory()
        async with factory() as session:
            yield session
    except Exception as e:
        logger.error(f"Database session creation failed: {e}")
        raise


