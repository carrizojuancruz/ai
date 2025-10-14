"""Test configuration for repositories tests."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest


@pytest.fixture
def mock_session():
    """Mock AsyncSession for database operations."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.execute = AsyncMock()
    session.get = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def sample_user_id():
    """Sample UUID for testing."""
    return uuid4()


@pytest.fixture
def reset_database_service_globals():
    """Reset DatabaseService singleton state before each test."""
    from app.repositories import database_service

    # Store original values
    original_instance = database_service.DatabaseService._instance
    original_session_factory = database_service.DatabaseService._session_factory
    original_user_repo = database_service.DatabaseService._user_repository
    original_finance_repo = database_service.DatabaseService._finance_repository

    # Reset globals
    database_service.DatabaseService._instance = None
    database_service.DatabaseService._session_factory = None
    database_service.DatabaseService._user_repository = None
    database_service.DatabaseService._finance_repository = None

    yield

    # Restore original values
    database_service.DatabaseService._instance = original_instance
    database_service.DatabaseService._session_factory = original_session_factory
    database_service.DatabaseService._user_repository = original_user_repo
    database_service.DatabaseService._finance_repository = original_finance_repo
