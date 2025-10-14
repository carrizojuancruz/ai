import pytest

from app.knowledge.management.sync_manager import KbSyncManager


@pytest.fixture
def mock_kb_service(mocker):
    mock_instance = mocker.MagicMock()
    mock_instance.upsert_source = mocker.AsyncMock()
    return mock_instance


@pytest.fixture
def sync_manager(mock_kb_service):
    manager = KbSyncManager()
    manager.knowledge_service = mock_kb_service
    return manager


@pytest.fixture
def mock_sync_service(mocker):
    mock = mocker.patch('app.knowledge.sync_service.KnowledgeBaseSyncService')
    mock_instance = mocker.MagicMock()
    mock_instance.sync_all = mocker.AsyncMock()
    mock.return_value = mock_instance
    return mock_instance
