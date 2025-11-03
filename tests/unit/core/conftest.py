"""Conftest for core module tests."""

import os
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    env_vars = {
        "AWS_REGION": "us-east-1",
        "DATABASE_HOST": "localhost",
        "DATABASE_PORT": "5432",
        "DATABASE_NAME": "test_db",
        "DATABASE_USER": "test_user",
        "DATABASE_PASSWORD": "test_password",
        "ENVIRONMENT": "test",
        "DEBUG": "false",
        "BEDROCK_EMBED_MODEL_ID": "amazon.titan-embed-text-v1",
        "S3V_BUCKET": "test-bucket",
        "S3V_INDEX_MEMORY": "memory-search",
        "S3V_INDEX_KB": "kb-index",
        "GUEST_AGENT_MODEL_ID": "test-model",
        "GUEST_AGENT_MODEL_REGION": "us-east-1",
        "SUPERVISOR_AGENT_MODEL_ID": "test-supervisor-model",
        "FINANCIAL_AGENT_MODEL_ID": "test-financial-model",
        "WEALTH_AGENT_MODEL_ID": "test-wealth-model",
        "GOAL_AGENT_MODEL_ID": "test-goal-model",
        "ONBOARDING_AGENT_MODEL_ID": "test-onboarding-model",
        "FOS_SECRETS_ID": "",
        "FOS_SECRETS_REGION": "us-east-1",
    }
    with patch.dict(os.environ, env_vars, clear=False):
        yield env_vars


@pytest.fixture
def mock_boto3_client():
    """Mock boto3 client for AWS services."""
    mock_client = Mock()
    mock_client.get_secret_value.return_value = {
        "SecretString": '{"test_key": "test_value"}'
    }
    return mock_client


@pytest.fixture
def mock_boto3_session():
    """Mock boto3 session."""
    with patch('boto3.session.Session') as mock_session:
        mock_session_instance = Mock()
        mock_session.return_value = mock_session_instance
        yield mock_session_instance


@pytest.fixture
def reset_app_state_globals():
    """Reset app_state global variables before each test."""
    import app.core.app_state as app_state

    original_values = {
        '_onboarding_agent': app_state._onboarding_agent,
        '_supervisor_graph': app_state._supervisor_graph,
        '_user_sessions': app_state._user_sessions.copy(),
        '_onboarding_threads': app_state._onboarding_threads.copy(),
        '_sse_queues': app_state._sse_queues.copy(),
        '_thread_locks': app_state._thread_locks.copy(),
        '_last_emitted_text': app_state._last_emitted_text.copy(),
        '_finance_samples_cache': app_state._finance_samples_cache.copy(),
        '_finance_agent_cache': app_state._finance_agent_cache.copy(),
        '_wealth_agent_cache': app_state._wealth_agent_cache.copy(),
        '_finance_agent': app_state._finance_agent,
        '_wealth_agent': app_state._wealth_agent,
        '_goal_agent': app_state._goal_agent,
        '_bedrock_runtime_client': app_state._bedrock_runtime_client,
        '_s3vectors_client': app_state._s3vectors_client,
        '_s3_client': app_state._s3_client,
        '_fos_nudge_manager': app_state._fos_nudge_manager,
    }

    app_state._onboarding_agent = None
    app_state._supervisor_graph = None
    app_state._user_sessions = {}
    app_state._onboarding_threads = {}
    app_state._sse_queues = {}
    app_state._thread_locks = {}
    app_state._last_emitted_text = {}
    app_state._finance_samples_cache = {}
    app_state._finance_agent_cache = {}
    app_state._wealth_agent_cache = {}
    app_state._finance_agent = None
    app_state._wealth_agent = None
    app_state._goal_agent = None
    app_state._bedrock_runtime_client = None
    app_state._s3vectors_client = None
    app_state._s3_client = None
    app_state._fos_nudge_manager = None

    yield

    app_state._onboarding_agent = original_values['_onboarding_agent']
    app_state._supervisor_graph = original_values['_supervisor_graph']
    app_state._user_sessions = original_values['_user_sessions']
    app_state._onboarding_threads = original_values['_onboarding_threads']
    app_state._sse_queues = original_values['_sse_queues']
    app_state._thread_locks = original_values['_thread_locks']
    app_state._last_emitted_text = original_values['_last_emitted_text']
    app_state._finance_samples_cache = original_values['_finance_samples_cache']
    app_state._finance_agent_cache = original_values['_finance_agent_cache']
    app_state._wealth_agent_cache = original_values['_wealth_agent_cache']
    app_state._finance_agent = original_values['_finance_agent']
    app_state._wealth_agent = original_values['_wealth_agent']
    app_state._goal_agent = original_values['_goal_agent']
    app_state._bedrock_runtime_client = original_values['_bedrock_runtime_client']
    app_state._s3vectors_client = original_values['_s3vectors_client']
    app_state._s3_client = original_values['_s3_client']
    app_state._fos_nudge_manager = original_values['_fos_nudge_manager']
