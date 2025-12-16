"""Configuration management for FOS-AI application.

Centralizes all environment variables and provides type-safe access to configuration values.
"""

import logging
import os
from typing import Optional, TypeVar

from app.core.aws_config import AWSConfig

logger = logging.getLogger(__name__)

T = TypeVar('T', int, float, bool)

LEGACY_SUMMARY_ENV_KEYS: tuple[str, ...] = (
    "SUMMARY_MAX_TOKENS",
    "SUMMARY_MAX_TOKENS_BEFORE",
)
_legacy_summary_keys_present: list[str] = [k for k in LEGACY_SUMMARY_ENV_KEYS if os.getenv(k) is not None]
if _legacy_summary_keys_present:
    logger.warning(
        "Legacy summarization env vars detected and ignored: %s",
        sorted(_legacy_summary_keys_present),
    )


def get_optional_value(env_var: str, cast_type: type[T]) -> Optional[T]:
    value = os.getenv(env_var)
    if value is None:
        return None
    if cast_type is bool:
        v = value.strip().lower()
        if v == "true":
            return True
        if v == "false":
            return False
        raise ValueError(f"Invalid boolean value for {env_var}: {value!r}. Must be 'true' or 'false'.")
    try:
        return cast_type(value)
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid value for environment variable '{env_var}': '{value}' cannot be cast to {cast_type.__name__}")
        raise ValueError(f"Configuration error: environment variable '{env_var}' has invalid value '{value}' for type {cast_type.__name__}") from e


class Config:
    """Centralized configuration class for managing environment variables.

    All configuration values should be accessed through this class instead of directly using os.getenv().
    """

    # Semantic Memory Merge Configuration
    MEMORY_MERGE_TOPK: Optional[int] = get_optional_value("MEMORY_MERGE_TOPK", int)
    MEMORY_MERGE_AUTO_UPDATE: Optional[float] = get_optional_value("MEMORY_MERGE_AUTO_UPDATE", float)
    MEMORY_MERGE_CHECK_LOW: Optional[float] = get_optional_value("MEMORY_MERGE_CHECK_LOW", float)
    MEMORY_MERGE_MODE: Optional[str] = os.getenv("MEMORY_MERGE_MODE")
    MEMORY_SEMANTIC_MIN_IMPORTANCE: Optional[int] = get_optional_value("MEMORY_SEMANTIC_MIN_IMPORTANCE", int)
    MEMORY_MERGE_FALLBACK_ENABLED: Optional[bool] = get_optional_value("MEMORY_MERGE_FALLBACK_ENABLED", bool)
    MEMORY_MERGE_FALLBACK_LOW: Optional[float] = get_optional_value("MEMORY_MERGE_FALLBACK_LOW", float)
    MEMORY_MERGE_FALLBACK_TOPK: Optional[int] = get_optional_value("MEMORY_MERGE_FALLBACK_TOPK", int)
    MEMORY_MERGE_FALLBACK_RECENCY_DAYS: Optional[int] = get_optional_value("MEMORY_MERGE_FALLBACK_RECENCY_DAYS", int)
    MEMORY_MERGE_FALLBACK_CATEGORIES: Optional[str] = os.getenv("MEMORY_MERGE_FALLBACK_CATEGORIES")

    # Episodic Memory Configuration
    EPISODIC_COOLDOWN_TURNS: Optional[int] = get_optional_value("EPISODIC_COOLDOWN_TURNS", int)
    EPISODIC_COOLDOWN_MINUTES: Optional[int] = get_optional_value("EPISODIC_COOLDOWN_MINUTES", int)
    EPISODIC_MAX_PER_DAY: Optional[int] = get_optional_value("EPISODIC_MAX_PER_DAY", int)
    EPISODIC_WINDOW_N: Optional[int] = get_optional_value("EPISODIC_WINDOW_N", int)
    EPISODIC_MERGE_WINDOW_HOURS: Optional[int] = get_optional_value("EPISODIC_MERGE_WINDOW_HOURS", int)
    EPISODIC_NOVELTY_MIN: Optional[float] = get_optional_value("EPISODIC_NOVELTY_MIN", float)
    MEMORY_TINY_LLM_MODEL_ID: str = os.getenv("MEMORY_TINY_LLM_MODEL_ID")

    MEMORY_SEMANTIC_MAX_LIMIT: Optional[int] = get_optional_value("MEMORY_SEMANTIC_MAX_LIMIT", int)
    MEMORY_EPISODIC_MAX_LIMIT: Optional[int] = get_optional_value("MEMORY_EPISODIC_MAX_LIMIT", int)

    # Cold Path Memory Configuration
    MEMORY_COLD_PATH_MAX_WORKERS: Optional[int] = get_optional_value("MEMORY_COLD_PATH_MAX_WORKERS", int)
    MEMORY_COLD_PATH_MAX_RETRIES: Optional[int] = get_optional_value("MEMORY_COLD_PATH_MAX_RETRIES", int)
    MEMORY_COLD_PATH_RETRY_BACKOFF_SECONDS: Optional[int] = get_optional_value("MEMORY_COLD_PATH_RETRY_BACKOFF_SECONDS", int)
    MEMORY_COLD_PATH_THREAD_STATE_TTL_SECONDS: Optional[int] = get_optional_value("MEMORY_COLD_PATH_THREAD_STATE_TTL_SECONDS", int)
    MEMORY_COLD_PATH_THREAD_STATE_CLEANUP_INTERVAL_SECONDS: Optional[int] = get_optional_value("MEMORY_COLD_PATH_THREAD_STATE_CLEANUP_INTERVAL_SECONDS", int)

    # Memory Context Configuration
    MEMORY_CONTEXT_TOPK: Optional[int] = get_optional_value("MEMORY_CONTEXT_TOPK", int)
    MEMORY_CONTEXT_TOPN: Optional[int] = get_optional_value("MEMORY_CONTEXT_TOPN", int)
    MEMORY_RERANK_WEIGHTS: str = os.getenv("MEMORY_RERANK_WEIGHTS")

    # Procedural Memory (Supervisor) Configuration
    MEMORY_PROCEDURAL_TOPK: Optional[int] = get_optional_value("MEMORY_PROCEDURAL_TOPK", int)
    MEMORY_PROCEDURAL_MIN_SCORE: Optional[float] = get_optional_value("MEMORY_PROCEDURAL_MIN_SCORE", float)

    # Conversation Summarization system
    SUMMARY_MAX_SUMMARY_TOKENS: Optional[int] = get_optional_value("SUMMARY_MAX_SUMMARY_TOKENS", int)
    SUMMARY_TRIGGER_PROMPT_TOKEN_COUNT: Optional[int] = get_optional_value("SUMMARY_TRIGGER_PROMPT_TOKEN_COUNT", int)
    SUMMARY_TRIGGER_USER_MESSAGE_COUNT_FALLBACK: Optional[int] = get_optional_value(
        "SUMMARY_TRIGGER_USER_MESSAGE_COUNT_FALLBACK",
        int,
    )
    SUMMARY_TAIL_TOKEN_BUDGET: Optional[int] = get_optional_value("SUMMARY_TAIL_TOKEN_BUDGET", int)
    SUMMARY_MODEL_ID: Optional[str] = os.getenv("SUMMARY_MODEL_ID")
    SUMMARY_MODEL_REGION: Optional[str] = os.getenv("SUMMARY_MODEL_REGION")
    SUMMARY_GUARDRAIL_ID: Optional[str] = os.getenv("SUMMARY_GUARDRAIL_ID")
    SUMMARY_GUARDRAIL_VERSION: Optional[str] = os.getenv("SUMMARY_GUARDRAIL_VERSION")

    # Finance Procedural (templates/hints for chartable SQL)
    FINANCE_PROCEDURAL_TOPK: Optional[int] = get_optional_value("FINANCE_PROCEDURAL_TOPK", int)
    FINANCE_PROCEDURAL_MIN_SCORE: Optional[float] = get_optional_value("FINANCE_PROCEDURAL_MIN_SCORE", float)

    # AWS Configuration
    AWS_REGION: str = os.getenv("AWS_REGION")
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")

    # Application Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT")
    REDIS_ENVIRONMENT: str = os.getenv("REDIS_ENVIRONMENT")
    DEBUG: Optional[bool] = get_optional_value("DEBUG", bool)

    # AI Models Configuration
    BEDROCK_EMBED_MODEL_ID: str = os.getenv("BEDROCK_EMBED_MODEL_ID")

    # Bedrock Retry Configuration
    BEDROCK_RETRY_MAX_ATTEMPTS: int = int(os.getenv("BEDROCK_RETRY_MAX_ATTEMPTS", "3"))

    # Wealth Agent Configuration
    WEALTH_AGENT_MODEL_ID: str = os.getenv("WEALTH_AGENT_MODEL_ID")
    WEALTH_AGENT_MODEL_REGION: str = os.getenv("WEALTH_AGENT_MODEL_REGION")
    WEALTH_AGENT_TEMPERATURE: Optional[float] = get_optional_value("WEALTH_AGENT_TEMPERATURE", float)
    WEALTH_AGENT_MAX_TOOL_CALLS: int = get_optional_value("WEALTH_AGENT_MAX_TOOL_CALLS", int) or 3
    WEALTH_AGENT_REASONING_EFFORT: str = os.getenv("WEALTH_AGENT_REASONING_EFFORT")
    WEALTH_AGENT_GUARDRAIL_ID: Optional[str] = os.getenv("WEALTH_AGENT_GUARDRAIL_ID")
    WEALTH_AGENT_GUARDRAIL_VERSION: Optional[str] = os.getenv("WEALTH_AGENT_GUARDRAIL_VERSION")

    CEREBRAS_API_KEY: str = os.getenv("CEREBRAS_API_KEY") or os.getenv("CEREBRAS_KEY")

    # Goal Agent Configuration
    GOAL_AGENT_MODEL_ID: str = os.getenv("GOAL_AGENT_MODEL_ID")
    GOAL_AGENT_PROVIDER: str = os.getenv("GOAL_AGENT_PROVIDER")
    GOAL_AGENT_MODEL_REGION: str = os.getenv("GOAL_AGENT_MODEL_REGION")
    GOAL_AGENT_TEMPERATURE: Optional[float] = get_optional_value("GOAL_AGENT_TEMPERATURE", float)
    GOAL_AGENT_GUARDRAIL_ID: Optional[str] = os.getenv("GOAL_AGENT_GUARDRAIL_ID")
    GOAL_AGENT_GUARDRAIL_VERSION: Optional[str] = os.getenv("GOAL_AGENT_GUARDRAIL_VERSION")

    # Financial Agent Configuration
    FINANCIAL_AGENT_MODEL_ID: str = os.getenv("FINANCIAL_AGENT_MODEL_ID")
    FINANCIAL_AGENT_MODEL_REGION: str = os.getenv("FINANCIAL_AGENT_MODEL_REGION")
    FINANCIAL_AGENT_TEMPERATURE: Optional[float] = get_optional_value("FINANCIAL_AGENT_TEMPERATURE", float)
    FINANCIAL_AGENT_REASONING_EFFORT: str = os.getenv("FINANCIAL_AGENT_REASONING_EFFORT")
    FINANCIAL_AGENT_GUARDRAIL_ID: Optional[str] = os.getenv("FINANCIAL_AGENT_GUARDRAIL_ID")
    FINANCIAL_AGENT_GUARDRAIL_VERSION: Optional[str] = os.getenv("FINANCIAL_AGENT_GUARDRAIL_VERSION")

    # Guest Agent Configuration
    GUEST_AGENT_MODEL_ID: str = os.getenv("GUEST_AGENT_MODEL_ID")
    GUEST_AGENT_MODEL_REGION: str = os.getenv("GUEST_AGENT_MODEL_REGION")
    GUEST_AGENT_TEMPERATURE: Optional[float] = get_optional_value("GUEST_AGENT_TEMPERATURE", float)
    GUEST_AGENT_REASONING_EFFORT: Optional[str] = os.getenv("GUEST_AGENT_REASONING_EFFORT")
    GUEST_AGENT_GUARDRAIL_ID: Optional[str] = os.getenv("GUEST_AGENT_GUARDRAIL_ID")
    GUEST_AGENT_GUARDRAIL_VERSION: Optional[str] = os.getenv("GUEST_AGENT_GUARDRAIL_VERSION")

    # Onboarding Agent Configuration
    ONBOARDING_AGENT_MODEL_ID: str = os.getenv("ONBOARDING_AGENT_MODEL_ID")
    ONBOARDING_AGENT_MODEL_REGION: str = os.getenv("ONBOARDING_AGENT_MODEL_REGION")
    ONBOARDING_AGENT_TEMPERATURE: Optional[float] = get_optional_value("ONBOARDING_AGENT_TEMPERATURE", float)
    ONBOARDING_AGENT_GUARDRAIL_ID: Optional[str] = os.getenv("ONBOARDING_AGENT_GUARDRAIL_ID")
    ONBOARDING_AGENT_GUARDRAIL_VERSION: Optional[str] = os.getenv("ONBOARDING_AGENT_GUARDRAIL_VERSION")

    # Supervisor Agent Configuration
    SUPERVISOR_AGENT_MODEL_ID: str = os.getenv("SUPERVISOR_AGENT_MODEL_ID")
    SUPERVISOR_AGENT_MODEL_REGION: str = os.getenv("SUPERVISOR_AGENT_MODEL_REGION")
    SUPERVISOR_AGENT_TEMPERATURE: Optional[float] = get_optional_value("SUPERVISOR_AGENT_TEMPERATURE", float)
    SUPERVISOR_AGENT_REASONING_EFFORT: str = os.getenv("SUPERVISOR_AGENT_REASONING_EFFORT")
    SUPERVISOR_AGENT_GUARDRAIL_ID: Optional[str] = os.getenv("SUPERVISOR_AGENT_GUARDRAIL_ID")
    SUPERVISOR_AGENT_GUARDRAIL_VERSION: Optional[str] = os.getenv("SUPERVISOR_AGENT_GUARDRAIL_VERSION")

    # Title Generation Configuration
    TITLE_GENERATOR_MODEL_ID: str = os.getenv("TITLE_GENERATOR_MODEL_ID")
    TITLE_GENERATOR_TEMPERATURE: Optional[float] = get_optional_value("TITLE_GENERATOR_TEMPERATURE", float)

    # S3 Vectors Configuration
    S3V_INDEX_MEMORY: str = os.getenv("S3V_INDEX_MEMORY")
    S3V_BUCKET: Optional[str] = os.getenv("S3V_BUCKET")
    S3V_INDEX_KB: Optional[str] = os.getenv("S3V_INDEX_KB")
    S3V_KB_S3_FILES: Optional[str] = os.getenv("S3V_KB_S3_FILES")
    S3V_DISTANCE: Optional[str] = os.getenv("S3V_DISTANCE")
    S3V_DIMS: Optional[int] = get_optional_value("S3V_DIMS", int)
    S3V_MAX_TOP_K: Optional[int] = get_optional_value("S3V_MAX_TOP_K", int)

    # Redis Configuration (populated exclusively via AWS Secrets -> aws_config)
    REDIS_HOST: Optional[str] = None
    REDIS_ENDPOINT: Optional[str] = None
    REDIS_PORT: Optional[str] = None
    REDIS_PASSWORD: Optional[str] = None
    REDIS_USERNAME: Optional[str] = None
    REDIS_ACCESS_STRING: Optional[str] = None
    REDIS_TLS: Optional[str] = None
    REDIS_TTL_DEFAULT: Optional[str] = None
    REDIS_TTL_SESSION: Optional[str] = None
    REDIS_TTL_SSE: Optional[str] = None

    # Langfuse Configuration (Guest)
    LANGFUSE_PUBLIC_KEY: Optional[str] = os.getenv("LANGFUSE_PUBLIC_KEY")
    LANGFUSE_SECRET_KEY: Optional[str] = os.getenv("LANGFUSE_SECRET_KEY")
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST")
    LANGFUSE_GUEST_PUBLIC_KEY: Optional[str] = os.getenv("LANGFUSE_GUEST_PUBLIC_KEY") or os.getenv(
        "LANGFUSE_PUBLIC_GUEST_KEY"
    )
    LANGFUSE_GUEST_SECRET_KEY: Optional[str] = os.getenv("LANGFUSE_GUEST_SECRET_KEY") or os.getenv(
        "LANGFUSE_SECRET_GUEST_KEY"
    )

    # Langfuse Configuration (Supervisor)
    LANGFUSE_PUBLIC_SUPERVISOR_KEY: Optional[str] = os.getenv("LANGFUSE_PUBLIC_SUPERVISOR_KEY")
    LANGFUSE_SECRET_SUPERVISOR_KEY: Optional[str] = os.getenv("LANGFUSE_SECRET_SUPERVISOR_KEY")
    LANGFUSE_TRACING_ENVIRONMENT: str = os.getenv("LANGFUSE_TRACING_ENVIRONMENT")

    # Langfuse Configuration (Goal)
    LANGFUSE_PUBLIC_GOAL_KEY: Optional[str] = os.getenv("LANGFUSE_PUBLIC_GOAL_KEY")
    LANGFUSE_SECRET_GOAL_KEY: Optional[str] = os.getenv("LANGFUSE_SECRET_GOAL_KEY")

    # Logging Configuration
    LOG_LEVEL: Optional[str] = os.getenv("LOG_LEVEL")
    LOG_SIMPLE: Optional[bool] = get_optional_value("LOG_SIMPLE", bool)
    LOG_DATEFMT: str = os.getenv("LOG_DATEFMT")
    LOG_QUIET_LIBS: Optional[bool] = get_optional_value("LOG_QUIET_LIBS", bool)
    LOG_LIB_LEVEL: Optional[str] = os.getenv("LOG_LIB_LEVEL")
    SUPERVISOR_TRACE_ENABLED: Optional[bool] = get_optional_value("SUPERVISOR_TRACE_ENABLED", bool)
    SUPERVISOR_TRACE_PATH: str = os.getenv("SUPERVISOR_TRACE_PATH")

    # Crawling Configuration
    CRAWL_TYPE: str = os.getenv("CRAWL_TYPE")
    CRAWL_TIMEOUT: Optional[int] = get_optional_value("CRAWL_TIMEOUT", int)

    VERA_GUIDANCE_URL: Optional[str] = os.getenv("VERA_GUIDANCE_URL")
    VERA_GUIDANCE_RECURSION_DEPTH: Optional[int] = get_optional_value("VERA_GUIDANCE_RECURSION_DEPTH", int)

    # Search Configuration
    TOP_K_SEARCH: Optional[int] = get_optional_value("TOP_K_SEARCH", int)
    CHUNK_SIZE: Optional[int] = get_optional_value("CHUNK_SIZE", int)
    CHUNK_OVERLAP: Optional[int] = get_optional_value("CHUNK_OVERLAP", int)

    # Guest Agent Configuration
    GUEST_MAX_MESSAGES: Optional[int] = get_optional_value("GUEST_MAX_MESSAGES", int)

    # Database Configuration
    DATABASE_HOST: str = os.getenv("DATABASE_HOST")
    DATABASE_PORT: str = os.getenv("DATABASE_PORT")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME")
    DATABASE_USER: str = os.getenv("DATABASE_USER")
    DATABASE_PASSWORD: str = os.getenv("DATABASE_PASSWORD")
    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")

    # External Services Configuration
    FOS_SERVICE_URL: Optional[str] = os.getenv("FOS_SERVICE_URL")
    FOS_API_KEY: Optional[str] = os.getenv("FOS_API_KEY")
    FOS_SECRETS_ID: Optional[str] = os.getenv("FOS_SECRETS_ID")
    FOS_SECRETS_REGION: str = os.getenv("FOS_SECRETS_REGION")

    # Prompt Service Configuration
    SUPERVISOR_PROMPT_TEST_MODE: Optional[bool] = get_optional_value("SUPERVISOR_PROMPT_TEST_MODE", bool)
    WEALTH_PROMPT_TEST_MODE: Optional[bool] = get_optional_value("WEALTH_PROMPT_TEST_MODE", bool)
    FINANCE_PROMPT_TEST_MODE: Optional[bool] = get_optional_value("FINANCE_PROMPT_TEST_MODE", bool)
    GUEST_PROMPT_TEST_MODE: Optional[bool] = get_optional_value("GUEST_PROMPT_TEST_MODE", bool)
    GOAL_PROMPT_TEST_MODE: Optional[bool] = get_optional_value("GOAL_PROMPT_TEST_MODE", bool)

    # Nudge System Configuration
    NUDGES_ENABLED: Optional[bool] = get_optional_value("NUDGES_ENABLED", bool)

    # FOS API Configuration
    FOS_USERS_PAGE_SIZE: Optional[int] = get_optional_value("FOS_USERS_PAGE_SIZE", int)
    FOS_USERS_MAX_PAGES: Optional[int] = get_optional_value("FOS_USERS_MAX_PAGES", int)

    # Evaluation Configuration
    EVAL_CONCURRENCY_LIMIT: Optional[int] = get_optional_value("EVAL_CONCURRENCY_LIMIT", int)

    # Bill Detection Configuration
    BILL_DETECTION_LOOKBACK_DAYS: Optional[int] = get_optional_value("BILL_DETECTION_LOOKBACK_DAYS", int)
    BILL_MIN_OCCURRENCES: Optional[int] = get_optional_value("BILL_MIN_OCCURRENCES", int)
    BILL_PREDICTION_WINDOW_DAYS: Optional[int] = get_optional_value("BILL_PREDICTION_WINDOW_DAYS", int)

    # SQS Configuration
    SQS_NUDGES_AI_INFO_BASED: Optional[str] = os.getenv("SQS_NUDGES_AI_INFO_BASED")
    SQS_QUEUE_REGION: str = os.getenv("SQS_QUEUE_REGION")
    SQS_MAX_MESSAGES: Optional[int] = get_optional_value("SQS_MAX_MESSAGES", int)
    SQS_VISIBILITY_TIMEOUT: Optional[int] = get_optional_value("SQS_VISIBILITY_TIMEOUT", int)
    SQS_WAIT_TIME_SECONDS: Optional[int] = get_optional_value("SQS_WAIT_TIME_SECONDS", int)

    # Audio Configuration
    AUDIO_ENABLED: Optional[bool] = get_optional_value("AUDIO_ENABLED", bool)
    TTS_PROVIDER: Optional[str] = os.getenv("TTS_PROVIDER")
    TTS_VOICE_ID: str = os.getenv("TTS_VOICE_ID")
    TTS_OUTPUT_FORMAT: str = os.getenv("TTS_OUTPUT_FORMAT")
    TTS_ENGINE: str = os.getenv("TTS_ENGINE")
    TTS_CHUNK_SIZE: Optional[int] = get_optional_value("TTS_CHUNK_SIZE", int)

    # STT Configuration
    STT_PROVIDER: Optional[str] = os.getenv("STT_PROVIDER")
    STT_MODEL_ID: Optional[str] = os.getenv("STT_MODEL_ID") # Bedrock

    # OpenAI Configuration (TTS, STT)
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_TTS_VOICE: Optional[str] = os.getenv("OPENAI_TTS_VOICE")
    OPENAI_TTS_MODEL: Optional[str] = os.getenv("OPENAI_TTS_MODEL")
    OPENAI_TTS_INSTRUCTIONS: Optional[str] = os.getenv("OPENAI_TTS_INSTRUCTIONS")
    OPENAI_STT_MODEL: Optional[str] = os.getenv("OPENAI_STT_MODEL")

    # Fallback configuration
    MODEL_STATE: str = os.getenv("MODEL_STATE")
    MODEL_REGION_ACTIVE: str = os.getenv("MODEL_REGION_ACTIVE")
    MODEL_GUARDRAIL_ACTIVE: str = os.getenv("MODEL_GUARDRAIL_ACTIVE")
    MODEL_GUARDRAIL_VERSION_ACTIVE: str = os.getenv("MODEL_GUARDRAIL_VERSION_ACTIVE")
    MODEL_REGION_STANDBY: str = os.getenv("MODEL_REGION_STANDBY")
    MODEL_GUARDRAIL_STANDBY: str = os.getenv("MODEL_GUARDRAIL_STANDBY")
    MODEL_GUARDRAIL_VERSION_STANDBY: str = os.getenv("MODEL_GUARDRAIL_VERSION_STANDBY")

    def __init__(self):
        self.__class__._initialize()

    @classmethod
    def _initialize(cls):
        secrets = AWSConfig(cls.FOS_SECRETS_REGION, cls.FOS_SECRETS_ID).get_secrets_manager_values()

        if secrets:
            for key, value in secrets.items():
                cls.set_env_var(key, value)

            secret_cerebras_key = secrets.get("CEREBRAS_API_KEY") or secrets.get("CEREBRAS_KEY")
            if secret_cerebras_key and not cls.CEREBRAS_API_KEY:
                cls.CEREBRAS_API_KEY = str(secret_cerebras_key)
                os.environ.setdefault("CEREBRAS_API_KEY", str(secret_cerebras_key))

        cls.MODEL_STATE = secrets.get("MODEL_STATE", cls.MODEL_STATE)

        if cls.MODEL_STATE == "ACTIVE":
            region = cls.MODEL_REGION_ACTIVE
            guardrail = cls.MODEL_GUARDRAIL_ACTIVE
            version = cls.MODEL_GUARDRAIL_VERSION_ACTIVE
        else:
            region = cls.MODEL_REGION_STANDBY
            guardrail = cls.MODEL_GUARDRAIL_STANDBY
            version = cls.MODEL_GUARDRAIL_VERSION_STANDBY

        gpt_agents = ["WEALTH_AGENT", "FINANCIAL_AGENT", "SUPERVISOR_AGENT", "SUMMARY"]

        for prefix in gpt_agents:
            region_attr = f"{prefix}_MODEL_REGION"
            guardrail_attr = f"{prefix}_GUARDRAIL_ID"
            version_attr = f"{prefix}_GUARDRAIL_VERSION"

            current_region = getattr(cls, region_attr, None)
            if not current_region or (isinstance(current_region, str) and not current_region.strip()):
                setattr(cls, region_attr, region)

            current_guardrail = getattr(cls, guardrail_attr, None)
            if not current_guardrail or (isinstance(current_guardrail, str) and not current_guardrail.strip()):
                setattr(cls, guardrail_attr, guardrail)

            current_version = getattr(cls, version_attr, None)
            if not current_version or (isinstance(current_version, str) and not current_version.strip()):
                setattr(cls, version_attr, version)

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
            logger.error("Failed to set environment variable %s with value %s", key, value)

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
            cls.LANGFUSE_PUBLIC_SUPERVISOR_KEY and cls.LANGFUSE_SECRET_SUPERVISOR_KEY and cls.LANGFUSE_HOST
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
    def is_sqs_enabled(cls) -> bool:
        """Check if SQS is properly configured for nudge queue operations.

        Returns:
            bool: True if SQS_NUDGES_AI_INFO_BASED is configured, False otherwise

        """
        return bool(cls.SQS_NUDGES_AI_INFO_BASED)

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
                    "is_sqs_enabled",
                    "get_actual_config",
                    "reload_config",
                ]
            ):
                config_dict[attr_name] = getattr(cls, attr_name)

        return config_dict

    @classmethod
    def reload_config(cls) -> bool:
        """Reload configuration from AWS Secrets Manager and environment variables.

        This method:
        1. Reloads secrets from AWS Secrets Manager
        2. Reloads all class attributes from current environment variables
        3. Returns True if successful, False otherwise

        Returns:
            bool: True if reload was successful, False otherwise

        """
        try:
            # Force reload of AWS secrets
            cls._initialize()

            # Reload all class attributes from current environment variables
            cls._reload_from_environment()
            return True
        except (ValueError, TypeError, AttributeError) as e:
            logger.error("Failed to reload config: %s", e)
            return False

    @classmethod
    def _reload_from_environment(cls):
        """Reload all class attributes from current environment variables."""
        # Get ALL configuration attributes automatically
        config_attrs = []
        for attr_name in dir(cls):
            # Skip private attributes (start with _)
            if attr_name.startswith("_"):
                continue

            # Skip methods (callable attributes)
            if callable(getattr(cls, attr_name)):
                continue

            # Skip special Python attributes (start and end with __)
            if attr_name.startswith("__") and attr_name.endswith("__"):
                continue

            # This is a configuration variable
            config_attrs.append(attr_name)

        reloaded_count = 0
        for attr_name in config_attrs:
            env_value = os.getenv(attr_name)
            if env_value is not None:
                # Apply the same type conversion logic as set_env_var
                cls.set_env_var(attr_name, env_value)
                reloaded_count += 1

        logger.info("Reloaded %s configuration variables from environment", reloaded_count)

    @classmethod
    def reload_prompt_config(cls) -> dict[str, bool]:
        """Reload only prompt-related configuration variables from environment.

        This method reloads ONLY the prompt service and test mode variables without
        affecting other configuration values.

        Returns:
            dict: Dictionary with reloaded variables and their new values

        """
        prompt_vars = [
            "SUPERVISOR_PROMPT_TEST_MODE",
            "WEALTH_PROMPT_TEST_MODE",
            "FINANCE_PROMPT_TEST_MODE",
            "GUEST_PROMPT_TEST_MODE",
            "GOAL_PROMPT_TEST_MODE",
        ]

        reloaded = {}
        for var_name in prompt_vars:
            env_value = os.getenv(var_name)
            if env_value is not None:
                cls.set_env_var(var_name, env_value)
                reloaded[var_name] = getattr(cls, var_name)
                logger.info(f"Reloaded {var_name} = {reloaded[var_name]}")

        return reloaded

    @classmethod
    def get_prompt_config_status(cls) -> dict[str, any]:
        """Get current status of prompt configuration.

        Returns:
            dict: Current values of all prompt-related configuration

        """
        return {
            "SUPERVISOR_PROMPT_TEST_MODE": cls.SUPERVISOR_PROMPT_TEST_MODE,
            "WEALTH_PROMPT_TEST_MODE": cls.WEALTH_PROMPT_TEST_MODE,
            "FINANCE_PROMPT_TEST_MODE": cls.FINANCE_PROMPT_TEST_MODE,
            "GUEST_PROMPT_TEST_MODE": cls.GUEST_PROMPT_TEST_MODE,
            "GOAL_PROMPT_TEST_MODE": cls.GOAL_PROMPT_TEST_MODE,
        }


config = Config()
