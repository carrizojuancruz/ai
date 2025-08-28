"""Configuration management for FOS-AI application.

Centralizes all environment variables and provides type-safe access to configuration values.
"""

import os
from typing import Optional

from .aws_config import load_aws_secrets

load_aws_secrets()


class Config:
    """Centralized configuration class for managing environment variables.

    All configuration values should be accessed through this class instead of directly using os.getenv().
    """

    # Semantic Memory Merge Configuration
    MEMORY_MERGE_TOPK: int = int(os.getenv("MEMORY_MERGE_TOPK", "5"))
    MEMORY_MERGE_AUTO_UPDATE: float = float(os.getenv("MEMORY_MERGE_AUTO_UPDATE", "0.85"))
    MEMORY_MERGE_CHECK_LOW: float = float(os.getenv("MEMORY_MERGE_CHECK_LOW", "0.60"))
    MEMORY_MERGE_MODE: str = os.getenv("MEMORY_MERGE_MODE", "recreate")
    MEMORY_SEMANTIC_MIN_IMPORTANCE: int = int(os.getenv("MEMORY_SEMANTIC_MIN_IMPORTANCE", "1"))
    MEMORY_MERGE_FALLBACK_ENABLED: bool = os.getenv("MEMORY_MERGE_FALLBACK_ENABLED", "true").lower() == "true"
    MEMORY_MERGE_FALLBACK_LOW: float = float(os.getenv("MEMORY_MERGE_FALLBACK_LOW", "0.30"))
    MEMORY_MERGE_FALLBACK_TOPK: int = int(os.getenv("MEMORY_MERGE_FALLBACK_TOPK", "3"))
    MEMORY_MERGE_FALLBACK_RECENCY_DAYS: int = int(os.getenv("MEMORY_MERGE_FALLBACK_RECENCY_DAYS", "90"))
    MEMORY_MERGE_FALLBACK_CATEGORIES: str = os.getenv("MEMORY_MERGE_FALLBACK_CATEGORIES", "Personal,Goals")

    # Episodic Memory Configuration
    EPISODIC_COOLDOWN_TURNS: int = int(os.getenv("EPISODIC_COOLDOWN_TURNS", "3"))
    EPISODIC_COOLDOWN_MINUTES: int = int(os.getenv("EPISODIC_COOLDOWN_MINUTES", "10"))
    EPISODIC_MAX_PER_DAY: int = int(os.getenv("EPISODIC_MAX_PER_DAY", "5"))
    EPISODIC_WINDOW_N: int = int(os.getenv("EPISODIC_WINDOW_N", "10"))
    EPISODIC_MERGE_WINDOW_HOURS: int = int(os.getenv("EPISODIC_MERGE_WINDOW_HOURS", "48"))
    EPISODIC_NOVELTY_MIN: float = float(os.getenv("EPISODIC_NOVELTY_MIN", "0.90"))
    MEMORY_TINY_LLM_MODEL_ID: str = os.getenv("MEMORY_TINY_LLM_MODEL_ID", "amazon.nova-micro-v1:0")
    # Memory Context Configuration
    MEMORY_CONTEXT_TOPK: int = int(os.getenv("MEMORY_CONTEXT_TOPK", "24"))
    MEMORY_CONTEXT_TOPN: int = int(os.getenv("MEMORY_CONTEXT_TOPN", "5"))
    MEMORY_RERANK_WEIGHTS: str = os.getenv("MEMORY_RERANK_WEIGHTS", "sim=0.55,imp=0.20,recency=0.15,pinned=0.10")

    # AWS Configuration
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    AWS_DEFAULT_REGION: str = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")

    # Application Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in {"true", "1", "yes", "on"}

    # AI Models Configuration
    AGENT_MODEL_ID: str = os.getenv("AGENT_MODEL_ID", "anthropic.claude-sonnet-4-20250514-v1:0")
    EMBEDDINGS_MODEL_ID: str = os.getenv("EMBEDDINGS_MODEL_ID", "amazon.titan-embed-text-v2:0")
    BEDROCK_MODEL_ID: str = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0")
    BEDROCK_EMBED_MODEL_ID: str = os.getenv("BEDROCK_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")
    BEDROCK_GUARDRAIL_ID: Optional[str] = os.getenv("BEDROCK_GUARDRAIL_ID")
    BEDROCK_GUARDRAIL_VERSION: Optional[str] = os.getenv("BEDROCK_GUARDRAIL_VERSION")

    # LLM Configuration
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "bedrock")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))

    # S3 Vectors Configuration
    MEMORIES_INDEX_ID: Optional[str] = os.getenv("MEMORIES_INDEX_ID")
    EMBEDDING_INDEX_ID: Optional[str] = os.getenv("EMBEDDING_INDEX_ID")
    VECTOR_INDEX_NAME: str = os.getenv("VECTOR_INDEX_NAME", "web-sources")
    S3V_INDEX_MEMORY: str = os.getenv("S3V_INDEX_MEMORY", "memory-search")
    S3V_BUCKET: Optional[str] = os.getenv("S3V_BUCKET")
    S3V_INDEX_KB: Optional[str] = os.getenv("S3V_INDEX_KB")
    S3V_DISTANCE: str = os.getenv("S3V_DISTANCE", "cosine").upper()
    S3V_DIMS: int = int(os.getenv("S3V_DIMS", "1024"))

    # Langfuse Configuration (Guest)
    LANGFUSE_PUBLIC_KEY: Optional[str] = os.getenv("LANGFUSE_PUBLIC_KEY")
    LANGFUSE_SECRET_KEY: Optional[str] = os.getenv("LANGFUSE_SECRET_KEY")
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "https://langfuse.promtior.ai")
    LANGFUSE_GUEST_PUBLIC_KEY: Optional[str] = os.getenv("LANGFUSE_GUEST_PUBLIC_KEY")
    LANGFUSE_GUEST_SECRET_KEY: Optional[str] = os.getenv("LANGFUSE_GUEST_SECRET_KEY")

    # Langfuse Configuration (Supervisor)
    LANGFUSE_PUBLIC_SUPERVISOR_KEY: Optional[str] = os.getenv("LANGFUSE_PUBLIC_SUPERVISOR_KEY")
    LANGFUSE_SECRET_SUPERVISOR_KEY: Optional[str] = os.getenv("LANGFUSE_SECRET_SUPERVISOR_KEY")
    LANGFUSE_HOST_SUPERVISOR: str = os.getenv("LANGFUSE_HOST_SUPERVISOR", "https://langfuse.promtior.ai")

    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_SIMPLE: bool = os.getenv("LOG_SIMPLE", "").lower() in {"1", "true", "yes", "on"}
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    LOG_DATEFMT: str = os.getenv("LOG_DATEFMT", "%Y-%m-%dT%H:%M:%S%z")
    LOG_QUIET_LIBS: bool = os.getenv("LOG_QUIET_LIBS", "").lower() in {"1", "true", "yes", "on"}
    LOG_LIB_LEVEL: str = os.getenv("LOG_LIB_LEVEL", "WARNING").upper()

    # Crawling Configuration
    CRAWL_TYPE: str = os.getenv("CRAWL_TYPE", "recursive")
    CRAWL_MAX_DEPTH: int = int(os.getenv("CRAWL_MAX_DEPTH", "3"))
    CRAWL_MAX_PAGES: int = int(os.getenv("CRAWL_MAX_PAGES", "50"))
    CRAWL_TIMEOUT: int = int(os.getenv("CRAWL_TIMEOUT", "30"))

    # Search Configuration
    TOP_K_SEARCH: int = int(os.getenv("TOP_K_SEARCH", "10"))
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1500"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))

    # Guest Agent Configuration
    GUEST_MAX_MESSAGES: int = int(os.getenv("GUEST_MAX_MESSAGES", "5"))

    # Database Configuration
    DATABASE_HOST: str = os.getenv("DATABASE_HOST")
    DATABASE_PORT: str = os.getenv("DATABASE_PORT")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME")
    DATABASE_USER: str = os.getenv("DATABASE_USER")
    DATABASE_PASSWORD: str = os.getenv("DATABASE_PASSWORD")

    # External Services Configuration
    FOS_SERVICE_URL: Optional[str] = os.getenv("FOS_SERVICE_URL")
    FOS_API_KEY: Optional[str] = os.getenv("FOS_API_KEY")
    FOS_SECRETS_ID: Optional[str] = os.getenv("FOS_SECRETS_ID")

    # Knowledge Base Configuration
    SOURCES_FILE_PATH: str = os.getenv("SOURCES_FILE_PATH", "./app/knowledge/sources/sources.json")

    @classmethod
    def get_aws_region(cls) -> str:
        """Get AWS region with fallback logic."""
        return cls.AWS_REGION or cls.AWS_DEFAULT_REGION

    @classmethod
    def get_database_url(cls) -> str:
        """Generate database URL if not provided via environment."""
        return f"postgresql+asyncpg://{cls.DATABASE_USER}:{cls.DATABASE_PASSWORD}@{cls.DATABASE_HOST}:{cls.DATABASE_PORT}/{cls.DATABASE_NAME}"

    @classmethod
    def is_langfuse_enabled(cls) -> bool:
        """Check if Langfuse is properly configured for guest."""
        return bool(cls.LANGFUSE_PUBLIC_KEY and cls.LANGFUSE_SECRET_KEY and cls.LANGFUSE_HOST)

    @classmethod
    def is_langfuse_supervisor_enabled(cls) -> bool:
        """Check if Langfuse is properly configured for supervisor."""
        return bool(
            cls.LANGFUSE_PUBLIC_SUPERVISOR_KEY
            and cls.LANGFUSE_SECRET_SUPERVISOR_KEY
            and cls.LANGFUSE_HOST_SUPERVISOR
        )

    @classmethod
    def get_bedrock_config(cls) -> dict:
        """Get Bedrock configuration dictionary."""
        return {
            "region": cls.get_aws_region(),
            "model_id": cls.BEDROCK_MODEL_ID,
            "temperature": cls.LLM_TEMPERATURE,
            "guardrail_id": cls.BEDROCK_GUARDRAIL_ID,
            "guardrail_version": cls.BEDROCK_GUARDRAIL_VERSION,
        }

    @classmethod
    def validate_required_s3_vars(cls) -> list[str]:
        """Validate required S3 variables and return missing ones."""
        required_vars = {
            "S3V_BUCKET": cls.S3V_BUCKET,
            "S3V_INDEX": cls.S3V_INDEX,
            "AWS_REGION": cls.get_aws_region(),
        }
        return [name for name, value in required_vars.items() if not value]

    @classmethod
    def get_actual_config(cls) -> dict[str, any]:
        """Get the actual configuration values."""
        config_dict = {}

        # Get all class attributes that are configuration variables
        for attr_name in dir(cls):
            # Skip private methods and built-in attributes
            if (not attr_name.startswith('_') and
                not callable(getattr(cls, attr_name)) and
                attr_name not in ['get_aws_region', 'get_database_url', 'is_langfuse_enabled',
                                'is_langfuse_supervisor_enabled', 'get_bedrock_config',
                                'validate_required_s3_vars', 'get_actual_config']):
                config_dict[attr_name] = getattr(cls, attr_name)

        return config_dict

# Create a singleton instance for easy import
config = Config()
