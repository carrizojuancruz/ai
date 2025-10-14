"""Conftest for db module tests."""

import asyncio
import contextlib
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


@pytest.fixture
def mock_engine():
    """Mock AsyncEngine for testing."""
    engine = Mock(spec=AsyncEngine)
    engine.dispose = AsyncMock()
    engine.begin = AsyncMock()

    mock_pool = Mock()
    mock_pool.size = Mock(return_value=10)
    mock_pool.checkedin = 5
    mock_pool.checkedout = 3
    mock_pool.invalid = 0
    mock_pool.overflow = 2
    engine.pool = mock_pool

    return engine


@pytest.fixture
def mock_session():
    """Mock AsyncSession for testing."""
    session = Mock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.close = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def mock_session_factory(mock_session):
    """Mock async_sessionmaker for testing."""
    factory = Mock()
    factory.return_value = mock_session
    return factory


@pytest.fixture
def reset_db_globals():
    """Reset db.session global variables before each test."""
    import app.db.session as session_module

    original_engine = session_module._engine
    original_factory = session_module._async_session_factory
    original_task = session_module._connection_health_check_task

    session_module._engine = None
    session_module._async_session_factory = None
    session_module._connection_health_check_task = None

    yield

    session_module._engine = original_engine
    session_module._async_session_factory = original_factory
    session_module._connection_health_check_task = original_task


@pytest.fixture
def mock_create_async_engine():
    """Mock create_async_engine function."""
    with patch('app.db.session.create_async_engine') as mock_create:
        yield mock_create


@pytest.fixture
def mock_async_sessionmaker():
    """Mock async_sessionmaker function."""
    with patch('app.db.session.async_sessionmaker') as mock_maker:
        yield mock_maker


@pytest.fixture
def mock_config():
    """Mock config for database tests."""
    with patch('app.db.session.config') as mock_cfg:
        mock_cfg.DATABASE_HOST = 'localhost'
        mock_cfg.DATABASE_PORT = '5432'
        mock_cfg.DATABASE_NAME = 'test_db'
        mock_cfg.DATABASE_USER = 'test_user'
        mock_cfg.DATABASE_PASSWORD = 'test_password'
        mock_cfg.get_database_url.return_value = 'postgresql+asyncpg://test_user:test_password@localhost:5432/test_db'
        yield mock_cfg


@pytest.fixture
async def cleanup_tasks():
    """Cleanup any running asyncio tasks after test."""
    yield
    tasks = [t for t in asyncio.all_tasks() if not t.done()]
    for task in tasks:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
