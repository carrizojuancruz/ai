"""Configuration management for FOS-AI application.

Centralizes all environment variables and provides type-safe access to configuration values.
"""

import os
from typing import Optional

from app.core.aws_config import AWSConfig


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
    MEMORY_TINY_LLM_MODEL_ID: str = os.getenv("MEMORY_TINY_LLM_MODEL_ID")
    # Memory Context Configuration
    MEMORY_CONTEXT_TOPK: int = int(os.getenv("MEMORY_CONTEXT_TOPK", "24"))
    MEMORY_CONTEXT_TOPN: int = int(os.getenv("MEMORY_CONTEXT_TOPN", "5"))
    MEMORY_RERANK_WEIGHTS: str = os.getenv("MEMORY_RERANK_WEIGHTS", "sim=0.55,imp=0.20,recency=0.15,pinned=0.10")

    # Procedural Memory (Supervisor) Configuration
    MEMORY_PROCEDURAL_TOPK: int = int(os.getenv("MEMORY_PROCEDURAL_TOPK", "3"))
    MEMORY_PROCEDURAL_MIN_SCORE: float = float(os.getenv("MEMORY_PROCEDURAL_MIN_SCORE", "0.45"))

    # AWS Configuration
    AWS_REGION: str = os.getenv("AWS_REGION")
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")

    # Application Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in {"true", "1", "yes", "on"}

    # AI Models Configuration
    BEDROCK_EMBED_MODEL_ID: str = os.getenv("BEDROCK_EMBED_MODEL_ID", "amazon.titan-embed-text-v1")

    # LLM Configuration
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "bedrock")

    # Wealth Agent Configuration
    WEALTH_AGENT_MODEL_ID: str = os.getenv("WEALTH_AGENT_MODEL_ID")
    WEALTH_AGENT_GUARDRAIL_ID: Optional[str] = os.getenv("WEALTH_AGENT_GUARDRAIL_ID")
    WEALTH_AGENT_GUARDRAIL_VERSION: str = os.getenv("WEALTH_AGENT_GUARDRAIL_VERSION")
    WEALTH_AGENT_MODEL_REGION: str = os.getenv("WEALTH_AGENT_MODEL_REGION")
    WEALTH_AGENT_TEMPERATURE: float = float(os.getenv("WEALTH_AGENT_TEMPERATURE", "0.2"))

    # Goal Agent Configuration
    GOAL_AGENT_MODEL_ID: str = os.getenv("GOAL_AGENT_MODEL_ID")
    GOAL_AGENT_GUARDRAIL_ID: Optional[str] = os.getenv("GOAL_AGENT_GUARDRAIL_ID")
    GOAL_AGENT_GUARDRAIL_VERSION: str = os.getenv("GOAL_AGENT_GUARDRAIL_VERSION")
    GOAL_AGENT_MODEL_REGION: str = os.getenv("GOAL_AGENT_MODEL_REGION")
    GOAL_AGENT_TEMPERATURE: float = float(os.getenv("GOAL_AGENT_TEMPERATURE", "0.2"))

    # Financial Agent Configuration
    FINANCIAL_AGENT_MODEL_ID: str = os.getenv("FINANCIAL_AGENT_MODEL_ID")
    FINANCIAL_AGENT_GUARDRAIL_ID: Optional[str] = os.getenv("FINANCIAL_AGENT_GUARDRAIL_ID")
    FINANCIAL_AGENT_GUARDRAIL_VERSION: str = os.getenv("FINANCIAL_AGENT_GUARDRAIL_VERSION")
    FINANCIAL_AGENT_MODEL_REGION: str = os.getenv("FINANCIAL_AGENT_MODEL_REGION")
    FINANCIAL_AGENT_TEMPERATURE: float = float(os.getenv("FINANCIAL_AGENT_TEMPERATURE", "0.2"))

    # Guest Agent Configuration
    GUEST_AGENT_MODEL_ID: str = os.getenv("GUEST_AGENT_MODEL_ID")
    GUEST_AGENT_GUARDRAIL_ID: Optional[str] = os.getenv("GUEST_AGENT_GUARDRAIL_ID")
    GUEST_AGENT_GUARDRAIL_VERSION: str = os.getenv("GUEST_AGENT_GUARDRAIL_VERSION")
    GUEST_AGENT_MODEL_REGION: str = os.getenv("GUEST_AGENT_MODEL_REGION")
    GUEST_AGENT_TEMPERATURE: float = float(os.getenv("GUEST_AGENT_TEMPERATURE", "0.2"))

    # Onboarding Agent Configuration
    ONBOARDING_AGENT_MODEL_ID: str = os.getenv("ONBOARDING_AGENT_MODEL_ID")
    ONBOARDING_AGENT_GUARDRAIL_ID: Optional[str] = os.getenv("ONBOARDING_AGENT_GUARDRAIL_ID")
    ONBOARDING_AGENT_GUARDRAIL_VERSION: str = os.getenv("ONBOARDING_AGENT_GUARDRAIL_VERSION")
    ONBOARDING_AGENT_MODEL_REGION: str = os.getenv("ONBOARDING_AGENT_MODEL_REGION")
    ONBOARDING_AGENT_TEMPERATURE: float = float(os.getenv("ONBOARDING_AGENT_TEMPERATURE", "0.2"))

    # Supervisor Agent Configuration
    SUPERVISOR_AGENT_MODEL_ID: str = os.getenv("SUPERVISOR_AGENT_MODEL_ID")
    SUPERVISOR_AGENT_GUARDRAIL_ID: Optional[str] = os.getenv("SUPERVISOR_AGENT_GUARDRAIL_ID")
    SUPERVISOR_AGENT_GUARDRAIL_VERSION: str = os.getenv("SUPERVISOR_AGENT_GUARDRAIL_VERSION")
    SUPERVISOR_AGENT_MODEL_REGION: str = os.getenv("SUPERVISOR_AGENT_MODEL_REGION")
    SUPERVISOR_AGENT_TEMPERATURE: float = float(os.getenv("SUPERVISOR_AGENT_TEMPERATURE", "0.2"))

    # S3 Vectors Configuration
    MEMORIES_INDEX_ID: Optional[str] = os.getenv("MEMORIES_INDEX_ID")
    EMBEDDING_INDEX_ID: Optional[str] = os.getenv("EMBEDDING_INDEX_ID")
    S3V_INDEX_MEMORY: str = os.getenv("S3V_INDEX_MEMORY", "memory-search")
    S3V_BUCKET: Optional[str] = os.getenv("S3V_BUCKET")
    S3V_INDEX_KB: Optional[str] = os.getenv("S3V_INDEX_KB")
    S3V_DISTANCE: str = os.getenv("S3V_DISTANCE", "cosine").upper()
    S3V_DIMS: int = int(os.getenv("S3V_DIMS", "1024"))
    S3V_MAX_TOP_K: int = int(os.getenv("S3V_MAX_TOP_K", "30"))

    # Langfuse Configuration (Guest)
    LANGFUSE_PUBLIC_KEY: Optional[str] = os.getenv("LANGFUSE_PUBLIC_KEY")
    LANGFUSE_SECRET_KEY: Optional[str] = os.getenv("LANGFUSE_SECRET_KEY")
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "https://langfuse.promtior.ai")
    LANGFUSE_GUEST_PUBLIC_KEY: Optional[str] = os.getenv("LANGFUSE_PUBLIC_GUEST_KEY")
    LANGFUSE_GUEST_SECRET_KEY: Optional[str] = os.getenv("LANGFUSE_SECRET_GUEST_KEY")

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
    CRAWL_MAX_DEPTH: int = int(os.getenv("CRAWL_MAX_DEPTH", "2"))
    CRAWL_MAX_PAGES: int = int(os.getenv("CRAWL_MAX_PAGES", "20"))
    CRAWL_TIMEOUT: int = int(os.getenv("CRAWL_TIMEOUT", "30"))
    MAX_DOCUMENTS_PER_SOURCE: int = int(os.getenv("MAX_DOCUMENTS_PER_SOURCE", "20"))

    # Search Configuration
    TOP_K_SEARCH: int = int(os.getenv("TOP_K_SEARCH", "10"))
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1500"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))
    MAX_CHUNKS_PER_SOURCE: int = int(os.getenv("MAX_CHUNKS_PER_SOURCE", "150"))

    # Guest Agent Configuration
    GUEST_MAX_MESSAGES: int = int(os.getenv("GUEST_MAX_MESSAGES", "5"))

    # Database Configuration
    DATABASE_HOST: str = os.getenv("DATABASE_HOST")
    DATABASE_PORT: str = os.getenv("DATABASE_PORT")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME")
    DATABASE_USER: str = os.getenv("DATABASE_USER")
    DATABASE_PASSWORD: str = os.getenv("DATABASE_PASSWORD")
    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")
    DATABASE_TYPE: str = os.getenv("DATABASE_TYPE", "postgresql")

    # External Services Configuration
    FOS_SERVICE_URL: Optional[str] = os.getenv("FOS_SERVICE_URL")
    FOS_API_KEY: Optional[str] = os.getenv("FOS_API_KEY")
    FOS_SECRETS_ID: Optional[str] = os.getenv("FOS_SECRETS_ID")
    FOS_SECRETS_REGION: str = os.getenv("FOS_SECRETS_REGION", "us-east-1")

    # Knowledge Base Configuration
    SOURCES_FILE_PATH: str = os.getenv("SOURCES_FILE_PATH", "./app/knowledge/sources/sources.json")

    # Nudge System Configuration
    NUDGES_ENABLED: bool = os.getenv("NUDGES_ENABLED", "true").lower() == "true"
    NUDGES_TYPE2_ENABLED: bool = os.getenv("NUDGES_TYPE2_ENABLED", "true").lower() == "true"
    NUDGES_TYPE3_ENABLED: bool = os.getenv("NUDGES_TYPE3_ENABLED", "true").lower() == "true"

    # FOS API Configuration
    FOS_USERS_PAGE_SIZE: int = int(os.getenv("FOS_USERS_PAGE_SIZE", "500"))
    FOS_USERS_MAX_PAGES: int = int(os.getenv("FOS_USERS_MAX_PAGES", "100"))
    FOS_USERS_API_TIMEOUT_MS: int = int(os.getenv("FOS_USERS_API_TIMEOUT_MS", "5000"))

    # Evaluation Configuration
    EVAL_CONCURRENCY_LIMIT: int = int(os.getenv("EVAL_CONCURRENCY_LIMIT", "4"))
    NUDGE_EVAL_BATCH_SIZE: int = int(os.getenv("NUDGE_EVAL_BATCH_SIZE", "100"))
    NUDGE_EVAL_TIMEOUT: int = int(os.getenv("NUDGE_EVAL_TIMEOUT", "30"))

    # Bill Detection Configuration
    BILL_DETECTION_LOOKBACK_DAYS: int = int(os.getenv("BILL_DETECTION_LOOKBACK_DAYS", "120"))
    BILL_MIN_OCCURRENCES: int = int(os.getenv("BILL_MIN_OCCURRENCES", "3"))
    BILL_PREDICTION_WINDOW_DAYS: int = int(os.getenv("BILL_PREDICTION_WINDOW_DAYS", "35"))

    SQS_QUEUE_URL: str = os.getenv(
        "SQS_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/905418355862/fos-ai-dev-nudges"
    )
    SQS_QUEUE_REGION: str = os.getenv("SQS_QUEUE_REGION", "us-east-1")
    SQS_MAX_MESSAGES: int = int(os.getenv("SQS_MAX_MESSAGES", "10"))
    SQS_VISIBILITY_TIMEOUT: int = int(os.getenv("SQS_VISIBILITY_TIMEOUT", "300"))  # 5 minutes
    SQS_WAIT_TIME_SECONDS: int = int(os.getenv("SQS_WAIT_TIME_SECONDS", "20"))  # Long polling

    def __init__(self):
        self.__class__._initialize()

    @classmethod
    def _initialize(cls):
        secrets = AWSConfig(cls.FOS_SECRETS_REGION, cls.FOS_SECRETS_ID).get_secrets_manager_values()

        if secrets:
            for key, value in secrets.items():
                cls.set_env_var(key, value)

    @classmethod
    def set_env_var(cls, key: str, value: str):
        try:
            if isinstance(value, str):
                if value.lower() in ["true", "false"]:
                    value = value.lower() == "true"
                elif value.isdigit():
                    value = int(value)
                elif value.replace(".", "", 1).isdigit():
                    value = float(value)
            setattr(cls, key, value)
        except (ValueError, TypeError):
            print(f"Failed to set environment variable {key} with value {value}")

    @classmethod
    def get_aws_region(cls) -> str:
        """Get AWS region with fallback logic."""
        return cls.AWS_REGION

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
            cls.LANGFUSE_PUBLIC_SUPERVISOR_KEY and cls.LANGFUSE_SECRET_SUPERVISOR_KEY and cls.LANGFUSE_HOST_SUPERVISOR
        )

    @classmethod
    def get_bedrock_config(cls) -> dict:
        """Get Bedrock configuration dictionary."""
        return {
            "region": cls.get_aws_region(),
        }

    @classmethod
    def validate_required_s3_vars(cls) -> list[str]:
        """Validate required S3 variables and return missing ones."""
        required_vars = {
            "S3V_BUCKET": cls.S3V_BUCKET,
            "S3V_INDEX_MEMORY": cls.S3V_INDEX_MEMORY,
            "S3V_INDEX_KB": cls.S3V_INDEX_KB,
            "AWS_REGION": cls.get_aws_region(),
        }
        return [name for name, value in required_vars.items() if not value]

    @classmethod
    def get_actual_config(cls) -> dict[str, any]:
        """Get the actual configuration values."""
        config_dict = {}

        for attr_name in dir(cls):
            if (
                not attr_name.startswith("_")
                and not callable(getattr(cls, attr_name))
                and attr_name
                not in [
                    "get_aws_region",
                    "get_database_url",
                    "is_langfuse_enabled",
                    "is_langfuse_supervisor_enabled",
                    "get_bedrock_config",
                    "validate_required_s3_vars",
                    "get_actual_config",
                ]
            ):
                config_dict[attr_name] = getattr(cls, attr_name)

        return config_dict


config = Config()
