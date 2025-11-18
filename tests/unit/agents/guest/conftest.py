"""Conftest for guest agent tests."""

from unittest.mock import Mock, patch

import pytest

from app.core.config import config


@pytest.fixture
def mock_config():
    """Mock configuration for guest agent tests."""
    with (
        patch.object(config, "GUEST_AGENT_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0"),
        patch.object(config, "GUEST_AGENT_MODEL_REGION", "us-east-1"),
        patch.object(config, "GUEST_AGENT_GUARDRAIL_ID", "test-guardrail-id"),
        patch.object(config, "GUEST_AGENT_GUARDRAIL_VERSION", "1"),
        patch.object(config, "LANGFUSE_GUEST_PUBLIC_KEY", "test-public-key"),
        patch.object(config, "LANGFUSE_GUEST_SECRET_KEY", "test-secret-key"),
        patch.object(config, "LANGFUSE_HOST", "https://test.langfuse.com"),
        patch.object(config, "GUEST_MAX_MESSAGES", 5),
    ):
        yield config


@pytest.fixture
def mock_langfuse_callback():
    """Mock Langfuse callback handler."""
    mock_callback = Mock()
    return mock_callback


@pytest.fixture
def mock_chat_bedrock():
    """Mock ChatBedrock instance."""
    mock_bedrock = Mock()
    return mock_bedrock
