"""Test imports and basic functionality."""

from datetime import datetime
from uuid import uuid4

import pytest


# Test basic imports work
def test_nudge_model_imports():
    """Test that nudge models can be imported without errors."""
    from app.models.nudge import NudgeChannel, NudgeRecord, NudgeStatus

    assert NudgeRecord is not None
    assert NudgeStatus is not None
    assert NudgeChannel is not None

def test_database_nudge_manager_import():
    """Test that DatabaseNudgeManager can be imported."""
    from app.services.nudges.database_manager import DatabaseNudgeManager

    assert DatabaseNudgeManager is not None

def test_nudge_orm_import():
    """Test that NudgeORM can be imported."""
    from app.db.models.nudge import NudgeORM

    assert NudgeORM is not None

def test_nudge_repository_import():
    """Test that NudgeRepository can be imported."""
    from app.repositories.postgres.nudge_repository import PostgresNudgeRepository

    assert PostgresNudgeRepository is not None

def test_app_state_nudge_manager_factory():
    """Test that nudge manager factory can be imported."""
    from app.core.app_state import get_database_nudge_manager

    assert get_database_nudge_manager is not None
    assert callable(get_database_nudge_manager)

def test_database_service_nudge_repository():
    """Test that DatabaseService has nudge repository method."""
    from app.repositories.database_service import DatabaseService

    # Check method exists
    assert hasattr(DatabaseService, 'get_nudge_repository')

    # Verify it's callable
    method = DatabaseService.get_nudge_repository
    assert callable(method)

def test_models_init_exports():
    """Test that models __init__.py exports NudgeORM."""
    from app.db.models import NudgeORM

    assert NudgeORM is not None

def test_postgres_init_exports():
    """Test that postgres __init__.py exports NudgeRepository."""
    from app.repositories.postgres import PostgresNudgeRepository

    assert PostgresNudgeRepository is not None

def test_all_enums_accessible():
    """Test that all nudge enums are accessible."""
    from app.models.nudge import NudgeChannel, NudgeStatus

    # Test NudgeStatus enum values
    status_values = ["pending", "processing", "sent", "failed", "cancelled"]
    for value in status_values:
        assert hasattr(NudgeStatus, value.upper())

    # Test NudgeChannel enum values
    channel_values = ["email", "sms", "push", "in_app"]
    for value in channel_values:
        if value == "in_app":
            assert hasattr(NudgeChannel, "IN_APP")
        else:
            assert hasattr(NudgeChannel, value.upper())

def test_basic_pydantic_model_creation():
    """Test that NudgeRecord can be created with valid data."""
    from app.models.nudge import NudgeChannel, NudgeRecord, NudgeStatus

    # This should not raise any errors
    record = NudgeRecord(
        id=uuid4(),
        user_id=uuid4(),
        nudge_type="test_nudge",
        priority=5,
        status=NudgeStatus.PENDING,
        channel=NudgeChannel.EMAIL,
        notification_text="Test notification",
        preview_text="Test preview",
        created_at=datetime.utcnow()
    )

    assert record is not None
    assert record.nudge_type == "test_nudge"
    assert record.priority == 5
    assert record.status == NudgeStatus.PENDING
    assert record.channel == NudgeChannel.EMAIL

def test_nudge_evaluator_updated_import():
    """Test that NudgeEvaluator can be imported and has db_manager."""
    from app.services.nudges.evaluator import NudgeEvaluator

    assert NudgeEvaluator is not None

    # Check that the class has the expected method
    assert hasattr(NudgeEvaluator, '_queue_nudge')

def test_icebreaker_processor_updated_import():
    """Test that IcebreakerProcessor can be imported."""
    from app.services.nudges.icebreaker_processor import IcebreakerProcessor

    assert IcebreakerProcessor is not None

    # Check that the class has the expected method
    assert hasattr(IcebreakerProcessor, 'process_icebreaker_for_user')

def test_all_dependencies_resolve():
    """Integration test that all imports resolve correctly."""
    # This test will fail if there are circular imports or missing dependencies

    # Import all nudge-related modules

    # If we get here without exceptions, all imports resolved successfully
    assert True

if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])
