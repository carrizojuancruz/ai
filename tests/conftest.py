"""Root conftest.py for pytest configuration."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to Python path so 'app' module can be imported
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class MockClientError(Exception):
    """Mock ClientError that inherits from Exception and mimics botocore.exceptions.ClientError."""

    def __init__(self, error_response, operation_name):
        self.response = error_response
        self.operation_name = operation_name
        error = error_response.get("Error", {})
        code = error.get("Code", "Unknown")
        message = error.get("Message", "")
        formatted_message = f"An error occurred ({code}) when calling the {operation_name} operation: {message}"
        super().__init__(formatted_message)


class MockNoCredentialsError(Exception):
    """Mock NoCredentialsError that inherits from Exception."""

    pass


mock_botocore_exceptions = MagicMock()
mock_botocore_exceptions.ClientError = MockClientError
mock_botocore_exceptions.NoCredentialsError = MockNoCredentialsError
sys.modules["botocore"] = MagicMock()
sys.modules["botocore.client"] = MagicMock()
sys.modules["botocore.config"] = MagicMock()
sys.modules["botocore.exceptions"] = mock_botocore_exceptions
sys.modules["boto3"] = MagicMock()
sys.modules["boto3.session"] = MagicMock()

os.environ.setdefault("S3V_BUCKET", "test-bucket")
os.environ.setdefault("S3V_INDEX_MEMORY", "test-memory-index")
os.environ.setdefault("S3V_DIMS", "1024")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test-key")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("FOS_API_BASE_URL", "http://localhost:3000")
os.environ.setdefault("FOS_API_INTERNAL_TOKEN", "test-token")
os.environ.setdefault("LANGFUSE_PUBLIC_SUPERVISOR_KEY", "test-public-key")
os.environ.setdefault("LANGFUSE_SECRET_SUPERVISOR_KEY", "test-secret-key")
os.environ.setdefault("LANGFUSE_HOST", "http://localhost:3000")
os.environ.setdefault("LANGFUSE_TRACING_ENVIRONMENT", "test")
os.environ.setdefault("AWS_BEDROCK_MODEL_ID", "test-model")
os.environ.setdefault("AWS_BEDROCK_REGION", "us-east-1")
os.environ.setdefault("GUEST_AGENT_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0")
os.environ.setdefault("GUEST_AGENT_MODEL_REGION", "us-east-1")
os.environ.setdefault("MODEL_STATE", "STANDBY")
os.environ.setdefault("MODEL_GUARDRAIL_STANDBY", "test-guardrail-id")
os.environ.setdefault("MODEL_GUARDRAIL_VERSION_STANDBY", "DRAFT")
os.environ.setdefault("MODEL_REGION_STANDBY", "us-east-1")
os.environ.setdefault("LANGFUSE_GUEST_PUBLIC_KEY", "")
os.environ.setdefault("LANGFUSE_GUEST_SECRET_KEY", "")
os.environ.setdefault("GUEST_MAX_MESSAGES", "20")
os.environ.setdefault("NUDGES_ENABLED", "true")
os.environ.setdefault("S3V_MAX_TOP_K", "100")
os.environ.setdefault("S3V_DISTANCE", "EUCLIDEAN")
os.environ.setdefault("MAX_TOOL_CALLS", "10")
os.environ.setdefault("LOG_LEVEL", "INFO")
os.environ.setdefault("LOG_QUIET_LIBS", "true")
os.environ.setdefault("CRAWL_TYPE", "recursive")
os.environ.setdefault("CHUNK_SIZE", "1000")
os.environ.setdefault("CHUNK_OVERLAP", "200")
os.environ.setdefault("CRAWL_TIMEOUT", "30")
os.environ.setdefault("SQS_QUEUE_REGION", "us-east-1")
os.environ.setdefault("EVAL_CONCURRENCY_LIMIT", "5")
os.environ.setdefault("SUPERVISOR_MAX_ROUTING_EXAMPLES", "10")
os.environ.setdefault("EPISODIC_INTERVAL_MINUTES", "30")
os.environ.setdefault("EPISODIC_MAX_PER_DAY", "5")
os.environ.setdefault("EPISODIC_COOLDOWN_MINUTES", "30")
os.environ.setdefault("EPISODIC_COOLDOWN_TURNS", "3")
os.environ.setdefault("EPISODIC_WINDOW_N", "10")
os.environ.setdefault("MEMORY_CONTEXT_TOPK", "10")
os.environ.setdefault("MEMORY_SEMANTIC_MIN_IMPORTANCE", "3")
os.environ.setdefault("MEMORY_SEMANTIC_MAX_LIMIT", "120")
os.environ.setdefault("MEMORY_EPISODIC_MAX_LIMIT", "120")
os.environ.setdefault("MEMORY_PROCEDURAL_TOPK", "3")
os.environ.setdefault("MEMORY_PROCEDURAL_MIN_SCORE", "0.45")
os.environ.setdefault("MEMORY_COLD_PATH_MAX_WORKERS", "4")
os.environ.setdefault("MEMORY_COLD_PATH_MAX_RETRIES", "3")
os.environ.setdefault("MEMORY_COLD_PATH_RETRY_BACKOFF_SECONDS", "1")
os.environ.setdefault("MEMORY_COLD_PATH_THREAD_STATE_TTL_SECONDS", "3600")
os.environ.setdefault("MEMORY_COLD_PATH_THREAD_STATE_CLEANUP_INTERVAL_SECONDS", "300")
os.environ.setdefault("FINANCE_PROCEDURAL_TOP_K", "5")
os.environ.setdefault("FINANCE_PROCEDURAL_TOPK", "3")
os.environ.setdefault("FINANCE_PROCEDURAL_MIN_SCORE", "0.45")
os.environ.setdefault("MAX_CHUNKS_PER_SOURCE", "150")
os.environ.setdefault("BEDROCK_EMBED_MODEL_ID", "amazon.titan-embed-text-v1")
os.environ.setdefault("SUMMARY_MAX_SUMMARY_TOKENS", "256")
os.environ.setdefault("SUMMARY_TRIGGER_PROMPT_TOKEN_COUNT", "25000")
os.environ.setdefault("SUMMARY_TRIGGER_USER_MESSAGE_COUNT_FALLBACK", "20")
os.environ.setdefault("SUMMARY_TAIL_TOKEN_BUDGET", "3500")
os.environ.setdefault("FAST_PATH_ENABLED", "true")
os.environ.setdefault("FAST_PATH_MODEL_PROVIDER", "cerebras")
os.environ.setdefault("FAST_PATH_MODEL_ID", "gpt-oss-120b")
os.environ.setdefault("FAST_PATH_TEMPERATURE", "0.3")
os.environ.setdefault("INTENT_CLASSIFIER_CONFIDENCE_THRESHOLD", "0.7")
