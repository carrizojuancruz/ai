"""Root conftest.py for pytest configuration."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to Python path so 'app' module can be imported
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Mock AWS/botocore imports before any app imports
sys.modules['botocore'] = MagicMock()
sys.modules['botocore.client'] = MagicMock()
sys.modules['botocore.config'] = MagicMock()
sys.modules['botocore.exceptions'] = MagicMock()
sys.modules['boto3'] = MagicMock()
sys.modules['boto3.session'] = MagicMock()

# Set required environment variables for tests
os.environ.setdefault('S3V_BUCKET', 'test-bucket')
os.environ.setdefault('AWS_REGION', 'us-east-1')
os.environ.setdefault('AWS_ACCESS_KEY_ID', 'test-key')
os.environ.setdefault('AWS_SECRET_ACCESS_KEY', 'test-secret')
os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost:5432/test')
os.environ.setdefault('FOS_API_BASE_URL', 'http://localhost:3000')
os.environ.setdefault('FOS_API_INTERNAL_TOKEN', 'test-token')
os.environ.setdefault('LANGFUSE_PUBLIC_SUPERVISOR_KEY', 'test-public-key')
os.environ.setdefault('LANGFUSE_SECRET_SUPERVISOR_KEY', 'test-secret-key')
os.environ.setdefault('LANGFUSE_HOST_SUPERVISOR', 'http://localhost:3000')
os.environ.setdefault('AWS_BEDROCK_MODEL_ID', 'test-model')
os.environ.setdefault('AWS_BEDROCK_REGION', 'us-east-1')

# Guest agent environment variables
os.environ.setdefault('GUEST_AGENT_MODEL_ID', 'anthropic.claude-3-5-sonnet-20240620-v1:0')
os.environ.setdefault('GUEST_AGENT_MODEL_REGION', 'us-east-1')
os.environ.setdefault('GUEST_AGENT_GUARDRAIL_ID', 'test-guardrail-id')
os.environ.setdefault('GUEST_AGENT_GUARDRAIL_VERSION', 'DRAFT')
os.environ.setdefault('LANGFUSE_GUEST_PUBLIC_KEY', '')
os.environ.setdefault('LANGFUSE_GUEST_SECRET_KEY', '')
os.environ.setdefault('LANGFUSE_HOST', '')
os.environ.setdefault('GUEST_MAX_MESSAGES', '20')
