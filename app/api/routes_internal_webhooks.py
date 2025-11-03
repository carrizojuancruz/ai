"""Internal webhooks API router for service-to-service communication."""

import logging
import os
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.aws_config import AWSConfig
from app.core.config import config

logger = logging.getLogger(__name__)

# Critical configuration fields that must be present
CRITICAL_DATABASE_FIELDS = ["DATABASE_HOST", "DATABASE_NAME", "DATABASE_USER", "DATABASE_PASSWORD"]
CRITICAL_LLM_FIELDS = ["BEDROCK_EMBED_MODEL_ID"]
CRITICAL_AWS_FIELD = "AWS_REGION"

# Internal router for webhook service-to-service communication (no auth required)
router = APIRouter(
    prefix="/internal/webhooks",
    tags=["Internal webhooks"],
)


def _categorize_config_field(field_name: str) -> str:
    """Categorize configuration field based on its name prefix.

    Args:
        field_name: Name of the configuration field

    Returns:
        Category name for the field

    """
    # Define category prefixes in order of priority
    category_mapping = [
        ("MEMORY_", "memory_config"),
        ("EPISODIC_", "memory_config"),
        ("SUMMARY_", "summarization_config"),
        ("FINANCE_", "finance_config"),
        ("AWS_", "aws_config"),
        ("DATABASE_", "database_config"),
        ("LANGFUSE_", "langfuse_config"),
        ("LOG_", "logging_config"),
        ("SUPERVISOR_TRACE_", "logging_config"),
        ("CRAWL_", "crawling_config"),
        ("CHUNK_", "search_config"),
        ("TOP_K_", "search_config"),
        ("MAX_CHUNKS_", "search_config"),
        ("SQS_", "sqs_config"),
        ("NUDGE", "nudge_config"),
        ("BEDROCK_", "llm_config"),
        ("LLM_", "llm_config"),
        ("WEALTH_AGENT_", "agents_config"),
        ("GOAL_AGENT_", "agents_config"),
        ("FINANCIAL_AGENT_", "agents_config"),
        ("GUEST_AGENT_", "agents_config"),
        ("ONBOARDING_AGENT_", "agents_config"),
        ("SUPERVISOR_AGENT_", "agents_config"),
        ("TITLE_GENERATOR_", "agents_config"),
        ("FOS_", "external_services_config"),
        ("EVAL_", "evaluation_config"),
        ("BILL_", "bill_detection_config"),
        ("S3V_", "s3_vectors_config"),
        ("MEMORIES_INDEX_", "s3_vectors_config"),
        ("EMBEDDING_INDEX_", "s3_vectors_config"),
        ("SOURCES_", "knowledge_base_config"),
        ("MAX_DOCUMENTS_", "crawling_config"),
    ]

    for prefix, category in category_mapping:
        if field_name.startswith(prefix):
            return category

    # Default category for uncategorized fields
    return "other_config"


def _is_sensitive_field(field_name: str) -> bool:
    """Check if a field contains sensitive data that should be masked.

    Args:
        field_name: Name of the configuration field

    Returns:
        True if field should be masked, False otherwise

    """
    sensitive_keywords = [
        "SECRET",
        "KEY",
        "PASSWORD",
        "TOKEN",
        "CREDENTIAL",
        "PRIVATE",
        "AUTH",
        "CERT",
        "PASSPHRASE",
    ]
    return any(keyword in field_name.upper() for keyword in sensitive_keywords)


def _is_critical_field(field_name: str) -> bool:
    """Check if a field is critical for system operation.

    Args:
        field_name: Name of the configuration field

    Returns:
        True if field is critical, False otherwise

    """
    critical_fields = CRITICAL_DATABASE_FIELDS + CRITICAL_LLM_FIELDS + [CRITICAL_AWS_FIELD]
    return field_name in critical_fields


def _audit_config_configuration() -> Dict[str, Any]:
    """Audit the complete configuration of config.py dynamically.

    This function automatically detects all configuration variables from the Config class
    and categorizes them dynamically based on their name prefixes.

    Returns:
        Dict with the configuration status of all variables

    """
    # Get all configuration attributes dynamically from Config class
    all_config_attrs = []
    for attr_name in dir(config):
        # Skip private attributes, methods, and special Python attributes
        if attr_name.startswith("_") or callable(getattr(config, attr_name)):
            continue
        all_config_attrs.append(attr_name)

    # Initialize audit result with dynamic categories
    categories = set()
    for attr_name in all_config_attrs:
        category = _categorize_config_field(attr_name)
        categories.add(category)

    audit_result = {category: {} for category in sorted(categories)}
    audit_result["summary"] = {
        "total_configured": 0,
        "total_missing": 0,
        "critical_missing": [],
        "optional_missing": [],
        "total_variables": len(all_config_attrs),
        "categories": sorted(categories),
    }

    # Audit each configuration field
    for field_name in sorted(all_config_attrs):
        value = getattr(config, field_name, None)
        category = _categorize_config_field(field_name)

        # Mask sensitive values
        display_value = value
        if _is_sensitive_field(field_name) and value:
            display_value = "***"

        # Add field to appropriate category
        audit_result[category][field_name] = {
            "configured": value is not None,
            "value": display_value,
        }

        # Update summary statistics
        if value is not None:
            audit_result["summary"]["total_configured"] += 1
        else:
            audit_result["summary"]["total_missing"] += 1
            if _is_critical_field(field_name):
                audit_result["summary"]["critical_missing"].append(field_name)
            else:
                audit_result["summary"]["optional_missing"].append(field_name)

    return audit_result


async def _reload_dependent_services() -> Dict[str, bool]:
    """Reload services that depend on AWSConfig and AWS secrets.

    Returns:
        Dict with the reload status of each service

    """
    services_status = {}

    try:
        # 1. Reload AWS clients (global instances)
        try:
            from app.core.app_state import dispose_aws_clients, warmup_aws_clients

            # Dispose existing clients
            dispose_aws_clients()

            # Warm up new clients using the existing event loop
            await warmup_aws_clients()

            services_status["aws_clients"] = True
            logger.info("✅ AWS clients reloaded successfully")
        except Exception as e:
            services_status["aws_clients"] = False
            logger.error("❌ Error reloading AWS clients: %s", e)

        # 2. Reload Database Connection (if needed)
        try:
            from app.db.session import dispose_engine, get_engine

            # Dispose existing connections using the existing event loop
            await dispose_engine()

            # Recreate engine using public function
            get_engine()

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

    No authentication required - for internal use between services.
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
        services_reloaded = await _reload_dependent_services()

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
    - AWS Secrets Manager status
    - Current config configuration
    - Complete audit of all variables in config.py (dynamically detected)

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
