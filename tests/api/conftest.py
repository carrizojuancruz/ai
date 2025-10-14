"""Conftest for API tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app  # Assuming main.py has the FastAPI app


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_onboarding_service():
    """Mock for onboarding_service."""
    mock = MagicMock()
    mock.initialize = AsyncMock()
    mock.process_message = AsyncMock()
    mock.finalize = AsyncMock()
    return mock


@pytest.fixture
def mock_get_onboarding_status_for_user():
    """Mock for get_onboarding_status_for_user."""
    return MagicMock()


@pytest.fixture
def mock_get_thread_state():
    """Mock for get_thread_state."""
    return MagicMock()


@pytest.fixture
def mock_get_sse_queue():
    """Mock for get_sse_queue."""
    return MagicMock()


@pytest.fixture
def mock_drop_sse_queue():
    """Mock for drop_sse_queue."""
    return MagicMock()


@pytest.fixture
def mock_external_repo():
    """Mock for ExternalUserRepository."""
    mock = MagicMock()
    mock.get_by_id = AsyncMock()
    return mock


@pytest.fixture
def mock_langfuse_cost_service():
    """Mock for LangfuseCostService."""
    mock = MagicMock()
    mock.get_users_costs = AsyncMock()
    mock.get_all_users_daily_costs_grouped = AsyncMock()
    mock.get_guest_costs = AsyncMock()
    return mock


@pytest.fixture
def mock_crawler_service():
    """Mock for CrawlerService."""
    mock = MagicMock()
    mock.crawl_source = AsyncMock()
    return mock


@pytest.fixture
def mock_document_service():
    """Mock for DocumentService."""
    mock = MagicMock()
    mock.split_documents = MagicMock()
    return mock


@pytest.fixture
def mock_knowledge_base_sync_service():
    """Mock for KnowledgeBaseSyncService."""
    mock = MagicMock()
    mock.sync_all = AsyncMock()
    return mock


@pytest.fixture
def mock_guest_service():
    """Mock for GuestService."""
    mock = MagicMock()
    mock.initialize = AsyncMock()
    mock.process_message = AsyncMock()
    return mock


@pytest.fixture
def mock_knowledge_service():
    """Mock for KnowledgeService."""
    mock = MagicMock()
    mock.search = AsyncMock()
    mock.get_sources = MagicMock()
    mock.get_source_details = MagicMock()
    mock.delete_all_vectors = MagicMock()
    return mock


@pytest.fixture
def mock_nudge_evaluator():
    """Mock for NudgeEvaluator."""
    mock = MagicMock()
    mock._evaluate_single_user = AsyncMock()
    mock.evaluate_nudges_batch = AsyncMock()
    return mock


@pytest.fixture
def mock_sqs_manager():
    """Mock for SQSManager."""
    mock = MagicMock()
    mock.get_queue_depth = AsyncMock()
    return mock


@pytest.fixture
def mock_iter_active_users():
    """Mock for iter_active_users async generator."""
    async def mock_generator():
        yield ["user1", "user2"]
        yield ["user3"]

    return mock_generator


@pytest.fixture
def mock_supervisor_service():
    """Mock for supervisor_service."""
    mock = MagicMock()
    mock.initialize = AsyncMock()
    mock.process_message = AsyncMock()
    return mock


@pytest.fixture
def mock_debug_icebreaker_flow():
    """Mock for debug_icebreaker_flow."""
    return AsyncMock()
