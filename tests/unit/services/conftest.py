"""Fixtures for services tests."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_s3_vectors_store():
    """Mock S3VectorsStore for testing."""
    store = MagicMock()
    store.search = MagicMock(return_value=[])
    store.delete = MagicMock()
    return store


@pytest.fixture
def mock_bedrock_chat_model():
    """Mock ChatBedrockConverse for testing."""
    model = MagicMock()
    model.invoke = MagicMock()
    model.astream = AsyncMock()
    model.callbacks = None
    return model


@pytest.fixture(autouse=True)
def mock_config():
    """Mock configuration for ALL service tests automatically."""
    # Patch in all the places services import config from
    patches = [
        patch("app.services.memory_service.config"),
        patch("app.services.guest.service.config"),
        patch("app.services.llm.bedrock.config"),
        patch("app.services.llm.title_generator.config"),
        patch("app.services.external_context.http_client.config"),
    ]

    mocks = [p.start() for p in patches]

    # Configure all mock configs identically
    for mock_cfg in mocks:
        mock_cfg.S3V_BUCKET = "test-bucket"
        mock_cfg.S3V_INDEX_MEMORY = "test-index"
        mock_cfg.get_aws_region.return_value = "us-east-1"
        mock_cfg.GUEST_MAX_MESSAGES = 5
        mock_cfg.ONBOARDING_AGENT_MODEL_ID = "anthropic.claude-v2"
        mock_cfg.ONBOARDING_AGENT_TEMPERATURE = 0.7
        mock_cfg.TITLE_GENERATOR_MODEL_ID = "anthropic.claude-v2"
        mock_cfg.TITLE_GENERATOR_TEMPERATURE = 0.1
        mock_cfg.FOS_SERVICE_URL = "https://fos.example.com"
        mock_cfg.FOS_API_KEY = "test-api-key"

    yield mocks[0]  # Return first mock for convenience

    for p in patches:
        p.stop()


@pytest.fixture
def mock_session_store():
    """Mock session store for testing."""
    store = MagicMock()
    store.set_session = AsyncMock()
    store.get_session = AsyncMock(return_value={"guest": True})
    return store


@pytest.fixture
def mock_sse_queue():
    """Mock SSE queue for testing."""
    queue = AsyncMock()
    queue.put = AsyncMock()
    return queue
