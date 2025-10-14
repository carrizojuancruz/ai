"""Test configuration for db.models tests."""

import pytest


@pytest.fixture(autouse=True)
def reset_sqlalchemy_registry():
    """Reset SQLAlchemy registry before each test to avoid conflicts."""
    yield
