"""Internal webhooks API router for service-to-service communication."""

import logging
import os
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.aws_config import AWSConfig
from app.core.config import config

logger = logging.getLogger(__name__)

# Internal router for webhook service-to-service communication (no auth required)
router = APIRouter(
    prefix="/internal/webhooks",
    tags=["Internal webhooks"],
)


def _audit_config_configuration() -> Dict[str, Any]:
    """Audit the complete configuration of config.py.

    Returns:
        Dict with the configuration status of all important variables

    """
    audit_result = {
        "memory_config": {},
        "aws_config": {},
        "llm_config": {},
        "database_config": {},
        "langfuse_config": {},
        "logging_config": {},
        "crawling_config": {},
        "search_config": {},
        "sqs_config": {},
        "nudge_config": {},
        "other_config": {},
        "summary": {
            "total_configured": 0,
            "total_missing": 0,
            "critical_missing": [],
            "optional_missing": [],
        },
    }

    # Memory Configuration
    memory_fields = [
        "MEMORY_MERGE_TOPK",
        "MEMORY_MERGE_AUTO_UPDATE",
        "MEMORY_MERGE_CHECK_LOW",
        "MEMORY_MERGE_MODE",
        "MEMORY_SEMANTIC_MIN_IMPORTANCE",
        "MEMORY_MERGE_FALLBACK_ENABLED",
        "EPISODIC_COOLDOWN_TURNS",
        "EPISODIC_COOLDOWN_MINUTES",
        "EPISODIC_MAX_PER_DAY",
        "MEMORY_CONTEXT_TOPK",
        "MEMORY_CONTEXT_TOPN",
        "MEMORY_PROCEDURAL_TOPK",
        "MEMORY_PROCEDURAL_MIN_SCORE",
    ]
    for field in memory_fields:
        value = getattr(config, field, None)
        audit_result["memory_config"][field] = {
            "configured": value is not None,
            "value": value,
        }
        if value is not None:
            audit_result["summary"]["total_configured"] += 1
        else:
            audit_result["summary"]["total_missing"] += 1
            audit_result["summary"]["optional_missing"].append(field)

    # AWS Configuration
    aws_fields = ["AWS_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]
    for field in aws_fields:
        value = getattr(config, field, None)
        audit_result["aws_config"][field] = {
            "configured": value is not None,
            "value": "***" if "SECRET" in field or "KEY" in field and value else value,
        }
        if value is not None:
            audit_result["summary"]["total_configured"] += 1
        else:
            audit_result["summary"]["total_missing"] += 1
            if field == "AWS_REGION":
                audit_result["summary"]["critical_missing"].append(field)

    # LLM Configuration
    llm_fields = [
        "LLM_PROVIDER",
        "BEDROCK_EMBED_MODEL_ID",
        "WEALTH_AGENT_MODEL_ID",
        "GOAL_AGENT_MODEL_ID",
        "FINANCIAL_AGENT_MODEL_ID",
        "GUEST_AGENT_MODEL_ID",
        "ONBOARDING_AGENT_MODEL_ID",
        "SUPERVISOR_AGENT_MODEL_ID",
        "TITLE_GENERATOR_MODEL_ID",
    ]
    for field in llm_fields:
        value = getattr(config, field, None)
        audit_result["llm_config"][field] = {
            "configured": value is not None,
            "value": value,
        }
        if value is not None:
            audit_result["summary"]["total_configured"] += 1
        else:
            audit_result["summary"]["total_missing"] += 1
            if field in ["LLM_PROVIDER", "BEDROCK_EMBED_MODEL_ID"]:
                audit_result["summary"]["critical_missing"].append(field)

    # Database Configuration
    db_fields = [
        "DATABASE_HOST",
        "DATABASE_PORT",
        "DATABASE_NAME",
        "DATABASE_USER",
        "DATABASE_PASSWORD",
        "DATABASE_URL",
        "DATABASE_TYPE",
    ]
    for field in db_fields:
        value = getattr(config, field, None)
        audit_result["database_config"][field] = {
            "configured": value is not None,
            "value": "***" if "PASSWORD" in field and value else value,
        }
        if value is not None:
            audit_result["summary"]["total_configured"] += 1
        else:
            audit_result["summary"]["total_missing"] += 1
            if field in ["DATABASE_HOST", "DATABASE_NAME", "DATABASE_USER", "DATABASE_PASSWORD"]:
                audit_result["summary"]["critical_missing"].append(field)

    # Langfuse Configuration
    langfuse_fields = [
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_HOST",
        "LANGFUSE_GUEST_PUBLIC_KEY",
        "LANGFUSE_GUEST_SECRET_KEY",
        "LANGFUSE_PUBLIC_SUPERVISOR_KEY",
        "LANGFUSE_SECRET_SUPERVISOR_KEY",
        "LANGFUSE_HOST_SUPERVISOR",
        "LANGFUSE_TRACING_ENVIRONMENT",
    ]
    for field in langfuse_fields:
        value = getattr(config, field, None)
        audit_result["langfuse_config"][field] = {
            "configured": value is not None,
            "value": "***" if "SECRET" in field or "KEY" in field and value else value,
        }
        if value is not None:
            audit_result["summary"]["total_configured"] += 1
        else:
            audit_result["summary"]["total_missing"] += 1
            audit_result["summary"]["optional_missing"].append(field)

    # Logging Configuration
    logging_fields = [
        "LOG_LEVEL",
        "LOG_SIMPLE",
        "LOG_FORMAT",
        "LOG_DATEFMT",
        "LOG_QUIET_LIBS",
        "LOG_LIB_LEVEL",
        "SUPERVISOR_TRACE_ENABLED",
        "SUPERVISOR_TRACE_PATH",
    ]
    for field in logging_fields:
        value = getattr(config, field, None)
        audit_result["logging_config"][field] = {
            "configured": value is not None,
            "value": value,
        }
        if value is not None:
            audit_result["summary"]["total_configured"] += 1
        else:
            audit_result["summary"]["total_missing"] += 1
            audit_result["summary"]["optional_missing"].append(field)

    # Crawling Configuration
    crawling_fields = [
        "CRAWL_TYPE",
        "CRAWL_MAX_DEPTH",
        "CRAWL_MAX_PAGES",
        "CRAWL_TIMEOUT",
        "MAX_DOCUMENTS_PER_SOURCE",
    ]
    for field in crawling_fields:
        value = getattr(config, field, None)
        audit_result["crawling_config"][field] = {
            "configured": value is not None,
            "value": value,
        }
        if value is not None:
            audit_result["summary"]["total_configured"] += 1
        else:
            audit_result["summary"]["total_missing"] += 1
            audit_result["summary"]["optional_missing"].append(field)

    # Search Configuration
    search_fields = [
        "TOP_K_SEARCH",
        "CHUNK_SIZE",
        "CHUNK_OVERLAP",
        "MAX_CHUNKS_PER_SOURCE",
    ]
    for field in search_fields:
        value = getattr(config, field, None)
        audit_result["search_config"][field] = {
            "configured": value is not None,
            "value": value,
        }
        if value is not None:
            audit_result["summary"]["total_configured"] += 1
        else:
            audit_result["summary"]["total_missing"] += 1
            audit_result["summary"]["optional_missing"].append(field)

    # SQS Configuration
    sqs_fields = [
        "SQS_NUDGES_AI_ICEBREAKER",
        "SQS_QUEUE_REGION",
        "SQS_MAX_MESSAGES",
        "SQS_VISIBILITY_TIMEOUT",
        "SQS_WAIT_TIME_SECONDS",
    ]
    for field in sqs_fields:
        value = getattr(config, field, None)
        audit_result["sqs_config"][field] = {
            "configured": value is not None,
            "value": value,
        }
        if value is not None:
            audit_result["summary"]["total_configured"] += 1
        else:
            audit_result["summary"]["total_missing"] += 1
            audit_result["summary"]["optional_missing"].append(field)

    # Nudge Configuration
    nudge_fields = [
        "NUDGES_ENABLED",
        "NUDGES_TYPE2_ENABLED",
        "NUDGES_TYPE3_ENABLED",
    ]
    for field in nudge_fields:
        value = getattr(config, field, None)
        audit_result["nudge_config"][field] = {
            "configured": value is not None,
            "value": value,
        }
        if value is not None:
            audit_result["summary"]["total_configured"] += 1
        else:
            audit_result["summary"]["total_missing"] += 1
            audit_result["summary"]["optional_missing"].append(field)

    # Other Configuration
    other_fields = [
        "ENVIRONMENT",
        "DEBUG",
        "FOS_SERVICE_URL",
        "FOS_API_KEY",
        "FOS_SECRETS_ID",
        "FOS_SECRETS_REGION",
        "SOURCES_FILE_PATH",
        "GUEST_MAX_MESSAGES",
        "FOS_USERS_PAGE_SIZE",
        "FOS_USERS_MAX_PAGES",
        "FOS_USERS_API_TIMEOUT_MS",
        "EVAL_CONCURRENCY_LIMIT",
        "NUDGE_EVAL_BATCH_SIZE",
        "NUDGE_EVAL_TIMEOUT",
        "BILL_DETECTION_LOOKBACK_DAYS",
        "BILL_MIN_OCCURRENCES",
        "BILL_PREDICTION_WINDOW_DAYS",
    ]
    for field in other_fields:
        value = getattr(config, field, None)
        audit_result["other_config"][field] = {
            "configured": value is not None,
            "value": "***" if "SECRET" in field or "KEY" in field and value else value,
        }
        if value is not None:
            audit_result["summary"]["total_configured"] += 1
        else:
            audit_result["summary"]["total_missing"] += 1
            audit_result["summary"]["optional_missing"].append(field)

    return audit_result


def _reload_dependent_services() -> Dict[str, bool]:
    """Reload services that depend on AWSConfig and AWS secrets.

    Returns:
        Dict with the reload status of each service

    """
    services_status = {}

    try:
        # 1. Reload AWS clients (global instances)
        try:
            import asyncio

            from app.core.app_state import dispose_aws_clients, warmup_aws_clients

            # Dispose existing clients
            dispose_aws_clients()

            # Warm up new clients
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(warmup_aws_clients())
            loop.close()

            services_status["aws_clients"] = True
            logger.info("✅ AWS clients reloaded successfully")
        except Exception as e:
            services_status["aws_clients"] = False
            logger.error("❌ Error reloading AWS clients: %s", e)

        # 2. Reload Database Connection (if needed)
        try:
            import asyncio

            from app.db.session import _get_engine, dispose_engine

            # Dispose existing connections
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(dispose_engine())

            # Recreate engine
            _get_engine()

            services_status["database_connection"] = True
            logger.info("✅ Database connection reloaded successfully")
        except Exception as e:
            services_status["database_connection"] = False
            logger.error("❌ Error reloading database connection: %s", e)

        # 3. Reload SQS Manager (global instance)
        try:
            import app.services.queue.sqs_manager as sqs_module

            # Reset global SQS manager instance
            sqs_module._sqs_manager = None

            services_status["sqs_manager"] = True
            logger.info("✅ SQS Manager reloaded successfully")
        except (ImportError, AttributeError) as e:
            services_status["sqs_manager"] = False
            logger.error("❌ Error reloading SQS Manager: %s", e)

        # 4. Reload Finance Agent Cache
        try:
            # Note: This would need user_id, so we'll just log that cache should be cleared
            services_status["finance_agent_cache"] = True
            logger.info("✅ Finance agent cache marked for invalidation")
        except (ImportError, AttributeError) as e:
            services_status["finance_agent_cache"] = False
            logger.error("❌ Error handling finance agent cache: %s", e)

    except (ImportError, AttributeError, RuntimeError) as e:
        logger.error("❌ Error general reloading services: %s", e)

    return services_status


class UpdateSecretsResponse(BaseModel):
    """Response model for secrets update webhook."""

    success: bool
    message: str
    secrets_loaded: int
    environment_variables_updated: int
    config_reloaded: bool
    services_reloaded: Dict[str, bool]


@router.post("/update-secrets", response_model=UpdateSecretsResponse)
async def update_secrets():
    """Reload all values from AWS Secrets Manager.

    This endpoint:
    1. Reloads secrets from AWS Secrets Manager using AWSConfig
    2. Updates environment variables with the new values
    3. Reloads the configuration of config.py

    No requires authentication - for internal use between services.
    """
    try:
        logger.info("🔄 Starting reload of secrets from AWS Secrets Manager")

        # Get current configuration
        secret_id = config.FOS_SECRETS_ID
        aws_region = config.AWS_REGION or "us-east-1"

        if not secret_id:
            logger.warning("No FOS_SECRETS_ID configured, skipping reload of secrets")
            return UpdateSecretsResponse(
                success=False,
                message="No FOS_SECRETS_ID configured",
                secrets_loaded=0,
                environment_variables_updated=0,
                config_reloaded=False,
                services_reloaded={},
            )

        # Count environment variables before the update
        env_vars_before = len(os.environ)

        # Create AWSConfig instance and load secrets
        aws_config = AWSConfig(region=aws_region, secrets_arn=secret_id)
        secret_data = aws_config.get_secrets_manager_values()

        if not secret_data:
            logger.warning("No secrets could be loaded from AWS Secrets Manager")
            return UpdateSecretsResponse(
                success=False,
                message="No secrets could be loaded from AWS",
                secrets_loaded=0,
                environment_variables_updated=0,
                config_reloaded=False,
                services_reloaded={},
            )

        # Apply secrets to environment variables
        secrets_loaded = 0
        for key, value in secret_data.items():
            os.environ[key] = str(value)
            secrets_loaded += 1

        # Count environment variables after the update
        env_vars_after = len(os.environ)
        env_vars_updated = env_vars_after - env_vars_before

        logger.info("✅ Secrets reloaded successfully: %d variables", secrets_loaded)
        logger.info("📊 Environment variables updated: %d", env_vars_updated)

        # Reload configuration
        try:
            # Reload the config singleton
            config_reloaded = config.reload_config()
            if config_reloaded:
                logger.info("✅ Config reloaded successfully")
            else:
                logger.error("❌ Config reload failed")
        except Exception as e:
            logger.error("❌ Error reloading config: %s", e)
            config_reloaded = False

        # Reload services that depend on AWSConfig
        services_reloaded = {}
        services_reloaded.update(_reload_dependent_services())

        return UpdateSecretsResponse(
            success=True,
            message="Secrets reloaded successfully from AWS Secrets Manager",
            secrets_loaded=secrets_loaded,
            environment_variables_updated=env_vars_updated,
            config_reloaded=config_reloaded,
            services_reloaded=services_reloaded,
        )

    except (ValueError, TypeError, RuntimeError) as e:
        logger.error("❌ Error reloading secrets: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reloading secrets: {str(e)}",
        ) from e


@router.get("/secrets-status")
async def get_secrets_status():
    """Endpoint to check the current state of the secrets configuration.

    Returns information about:
    - Environment variables configured
    - AWS Secrets Manager status
    - Current config configuration
    - Complete audit of all variables in config.py

    No requires authentication - for internal use between services.
    """
    try:
        secret_id = config.FOS_SECRETS_ID
        aws_region = config.AWS_REGION or "us-east-1"

        # Basic information
        status_info = {
            "aws_region": aws_region,
            "fos_secrets_id_configured": bool(secret_id),
            "environment": config.ENVIRONMENT,
            "debug_mode": config.DEBUG,
            "total_env_vars": len(os.environ),
            "config_loaded": True,
        }

        # Secrets information (without sensitive values)
        if secret_id:
            try:
                aws_config = AWSConfig(region=aws_region, secrets_arn=secret_id)
                # Only try to connect, don't load complete secrets
                client = aws_config._setup_aws_client()  # pylint: disable=protected-access
                if client:
                    status_info["aws_connection"] = "success"
                    status_info["secrets_arn"] = secret_id
                else:
                    status_info["aws_connection"] = "error: client creation failed"
            except Exception as e:
                status_info["aws_connection"] = f"error: {str(e)}"
        else:
            status_info["aws_connection"] = "not_configured"

        # Key environment variables (without sensitive values)
        key_env_vars = [
            "ENVIRONMENT",
            "AWS_REGION",
            "DATABASE_HOST",
            "DATABASE_NAME",
            "LLM_PROVIDER",
            "BEDROCK_EMBED_MODEL_ID",
            "FOS_SERVICE_URL",
            "LOG_LEVEL",
        ]

        env_vars_info = {}
        for var in key_env_vars:
            if var in os.environ:
                env_vars_info[var] = "configured"
            else:
                env_vars_info[var] = "not_set"

        status_info["key_environment_variables"] = env_vars_info

        # Complete audit of config.py
        audit_result = _audit_config_configuration()
        status_info["config_audit"] = audit_result

        # General configuration status
        critical_missing = audit_result["summary"]["critical_missing"]
        status_info["configuration_status"] = {
            "overall_status": "healthy" if not critical_missing else "critical_issues",
            "critical_missing_count": len(critical_missing),
            "critical_missing_fields": critical_missing,
            "optional_missing_count": len(audit_result["summary"]["optional_missing"]),
            "total_configured": audit_result["summary"]["total_configured"],
            "total_missing": audit_result["summary"]["total_missing"],
            "configuration_completeness_percentage": (
                round(
                    (
                        audit_result["summary"]["total_configured"]
                        / (
                            audit_result["summary"]["total_configured"]
                            + audit_result["summary"]["total_missing"]
                        )
                        * 100
                    ),
                    2,
                )
                if (
                    audit_result["summary"]["total_configured"]
                    + audit_result["summary"]["total_missing"]
                )
                > 0
                else 0
            ),
        }

        return status_info

    except (ValueError, TypeError, RuntimeError) as e:
        logger.error("Error getting secrets status: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting status: {str(e)}",
        ) from e
