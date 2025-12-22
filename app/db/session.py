from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from typing import AsyncGenerator, Optional

from sqlalchemy import text
from sqlalchemy.exc import DisconnectionError, OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import config

logger = logging.getLogger(__name__)

DATABASE_URL = config.get_database_url()

_engine: Optional[AsyncEngine] = None
_async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None
_connection_health_check_task: Optional[asyncio.Task] = None


async def _health_check_connection(engine) -> bool:
    """Perform a health check on the database connection."""
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1 as health_check"))
            logger.debug("Database health check passed")
        return True
    except Exception as e:
        logger.warning(f"Database health check failed: {type(e).__name__}: {str(e)}")
        logger.warning(f"Connection details - Host: {config.DATABASE_HOST}:{config.DATABASE_PORT}, Database: {config.DATABASE_NAME}")
        logger.debug(f"Health check error details: {type(e).__name__}: {str(e)}")
        return False


async def _periodic_health_check():
    """Periodic health check for database connections."""
    while True:
        try:
            await asyncio.sleep(600)  # Check every 10 minutes (more reasonable)
            if _engine is not None:
                logger.debug("Running periodic database health check")
                is_healthy = await _health_check_connection(_engine)
                if not is_healthy:
                    logger.warning("Database connection unhealthy, attempting to reconnect...")
                    try:
                        await _reconnect_engine()
                    except Exception as reconnect_error:
                        logger.error(f"Database reconnection failed: {reconnect_error}")
                else:
                    logger.debug("Database connection is healthy")
        except asyncio.CancelledError:
            logger.info("Database health check task cancelled")
            break
        except Exception as e:
            logger.error(f"Health check task error: {e}")
            # Continue the loop even if there's an error


async def _reconnect_engine():
    """Reconnect the database engine."""
    global _engine, _async_session_factory

    try:
        if _engine is not None:
            await _engine.dispose()
            logger.info("Database engine disposed for reconnection")

        connect_args = {
            "server_settings": {
                "application_name": "verde-ai",
                "timezone": "UTC"
            },
            "timeout": 10.0,
            "command_timeout": 60.0,
            "ssl": "require",
        }

        _engine = create_async_engine(
            DATABASE_URL,
            echo=False,
            future=True,
            # Connection Pool Configuration
            pool_size=10,                    # Base pool size
            max_overflow=20,                 # Max additional connections
            pool_timeout=30,                 # Connection timeout (seconds)
            pool_recycle=1800,               # Recycle connections every 30 min
            pool_pre_ping=True,              # Health check before using connection
            # Connection Configuration for asyncpg
            connect_args=connect_args
        )

        # Recreate session factory
        _async_session_factory = async_sessionmaker(
            _engine,
            expire_on_commit=False,
            class_=AsyncSession
        )

        # Test the new connection
        is_healthy = await _health_check_connection(_engine)
        if is_healthy:
            logger.info("Database engine reconnected successfully")
        else:
            logger.error("Database reconnection failed health check")

    except Exception as e:
        logger.error(f"Database reconnection failed: {e}")
        raise


def _get_engine():
    """Lazy-load database engine with robust configuration."""
    global _engine, _connection_health_check_task
    if _engine is None:
        try:
            connect_args = {
                "server_settings": {
                    "application_name": "verde-ai",
                    "timezone": "UTC"
                },
                "timeout": 10.0,
                "command_timeout": 60.0,
                "ssl": "require",
            }

            _engine = create_async_engine(
                DATABASE_URL,
                echo=False,
                future=True,
                # Connection Pool Configuration
                pool_size=10,                    # Base pool size
                max_overflow=20,                 # Max additional connections
                pool_timeout=30,                 # Connection timeout (seconds)
                pool_recycle=1800,               # Recycle connections every 30 min
                pool_pre_ping=True,              # Health check before using connection
                # Connection Configuration for asyncpg
                connect_args=connect_args
            )

            # Start periodic health check
            if _connection_health_check_task is None:
                _connection_health_check_task = asyncio.create_task(_periodic_health_check())
                logger.info("Database health check task started")

            logger.info("Database engine created successfully with asyncpg configuration")

        except Exception as e:
            logger.error(f"Database engine creation failed: {type(e).__name__}: {str(e)}")
            logger.error(f"Database connection details - Host: {config.DATABASE_HOST}, Port: {config.DATABASE_PORT}, Database: {config.DATABASE_NAME}, User: {config.DATABASE_USER}")
            logger.error(f"Full database URL (masked): {DATABASE_URL.replace(DATABASE_URL.split('@')[0].split('://')[-1], '***:***')}")
            raise
    return _engine


def _get_session_factory():
    """Lazy-load session factory with error handling."""
    global _async_session_factory
    if _async_session_factory is None:
        try:
            _async_session_factory = async_sessionmaker(
                _get_engine(),
                expire_on_commit=False,
                class_=AsyncSession
            )
            logger.info("Database session factory created successfully")
        except Exception as e:
            logger.error(f"Database session factory creation failed: {e}")
            raise
    return _async_session_factory


async def _create_session_with_retry(max_retries: int = 3) -> AsyncSession:
    """Create a database session with retry mechanism."""
    factory = _get_session_factory()

    for attempt in range(max_retries):
        try:
            session = factory()
            # Test the session with a simple query
            await session.execute(text("SELECT 1"))
            return session
        except (OperationalError, DisconnectionError) as e:
            logger.warning(f"Database session creation failed (attempt {attempt + 1}/{max_retries}): {type(e).__name__}: {str(e)}")
            logger.warning(f"Connection details - Host: {config.DATABASE_HOST}:{config.DATABASE_PORT}, Database: {config.DATABASE_NAME}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                logger.info(f"Retrying in {2 ** attempt} seconds...")
                continue
            else:
                logger.error("All database session creation attempts failed")
                logger.error(f"Final error: {type(e).__name__}: {str(e)}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error creating database session: {type(e).__name__}: {str(e)}")
            logger.error(f"Connection details - Host: {config.DATABASE_HOST}:{config.DATABASE_PORT}, Database: {config.DATABASE_NAME}")
            raise


def get_engine():
    """Get database engine (lazy-loaded)."""
    return _get_engine()


def get_async_session_factory():
    """Get async session factory (lazy-loaded)."""
    return _get_session_factory()


@asynccontextmanager
async def get_robust_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a robust database session with automatic retry and error handling."""
    session = None
    try:
        session = await _create_session_with_retry()
        logger.debug("Database session acquired successfully")
        yield session
    except Exception as e:
        logger.error(f"Failed to acquire database session: {e}")
        raise
    finally:
        if session:
            try:
                await session.close()
                logger.debug("Database session closed successfully")
            except Exception as e:
                logger.warning(f"Error closing database session: {e}")


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session with robust error handling (legacy compatibility)."""
    async with get_robust_session() as session:
        yield session


async def dispose_engine():
    """Properly dispose of the database engine and cleanup resources."""
    global _engine, _connection_health_check_task

    try:
        if _connection_health_check_task and not _connection_health_check_task.done():
            _connection_health_check_task.cancel()
            with suppress(asyncio.CancelledError):
                await _connection_health_check_task
            logger.info("Database health check task cancelled")

        if _engine:
            await _engine.dispose()
            logger.info("Database engine disposed successfully")

    except Exception as e:
        logger.error(f"Error disposing database engine: {e}")
    finally:
        _engine = None
        _async_session_factory = None
        _connection_health_check_task = None


def get_connection_stats():
    """Get database connection pool statistics for monitoring."""
    if _engine is None:
        return None

    try:
        pool = _engine.pool
        return {
            "pool_size": getattr(pool, 'size', 0),
            "checked_in": getattr(pool, 'checkedin', 0),
            "checked_out": getattr(pool, 'checkedout', 0),
            "invalid": getattr(pool, 'invalid', 0),
            "overflow": getattr(pool, 'overflow', 0),
        }
    except Exception as e:
        logger.warning(f"Could not get connection stats: {e}")
        return None


