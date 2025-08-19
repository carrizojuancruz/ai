"""AWS configuration and secrets management."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def load_config_from_env() -> None:
    """Load configuration from a single FOS_CONFIG environment variable."""
    config_json = os.getenv("FOS_CONFIG")

    if not config_json:
        logger.info("No FOS_CONFIG found, using individual environment variables")
        return

    try:
        config = json.loads(config_json)
        loaded_count = 0
        for key, value in config.items():
            if key not in os.environ:
                os.environ[key] = str(value)
                logger.debug(f"Set environment variable: {key}")
                loaded_count += 1
            else:
                logger.debug(f"Skipping {key} - already set in environment")
        logger.info(f"Successfully loaded {loaded_count} configuration values from FOS_CONFIG")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse FOS_CONFIG JSON: {e}")
    except Exception as e:
        logger.error(f"Unexpected error loading configuration: {e}")


def load_aws_secrets(secret_arn: str | None = None, region: str = "us-east-1") -> None:
    """Load secrets from AWS Secrets Manager into environment variables."""
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
    except ImportError:
        logger.warning("boto3 not available, skipping AWS Secrets Manager loading")
        return

    if not secret_arn:
        secret_arn = os.getenv("FOS_SECRETS_ARN")

    if not secret_arn:
        logger.info("No AWS Secrets ARN provided, using local environment variables")
        return

    try:
        session = boto3.session.Session()
        client = session.client(service_name="secretsmanager", region_name=region)
        logger.info(f"Loading secrets from AWS Secrets Manager: {secret_arn}")
        response = client.get_secret_value(SecretId=secret_arn)
        if "SecretString" in response:
            secret_string = response["SecretString"]
        else:
            logger.error("Binary secrets are not supported")
            return
        os.environ["FOS_CONFIG"] = secret_string
        logger.info("Successfully loaded AWS secret into FOS_CONFIG")
        load_config_from_env()
        if "AWS_REGION" not in os.environ and "AWS_DEFAULT_REGION" not in os.environ:
            os.environ["AWS_DEFAULT_REGION"] = region
            logger.info(f"Set AWS_DEFAULT_REGION to {region}")
    except NoCredentialsError:
        logger.warning("AWS credentials not found, skipping Secrets Manager loading")
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ResourceNotFoundException":
            logger.error(f"Secret {secret_arn} not found")
        elif error_code == "AccessDeniedException":
            logger.error(f"Access denied to secret {secret_arn}")
        else:
            logger.error(f"Error retrieving secret: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse secret JSON: {e}")
    except Exception as e:
        logger.error(f"Unexpected error loading secrets: {e}")


def configure_aws_environment() -> dict[str, Any]:
    """Configure AWS environment and return configuration info."""
    config = {
        "region": os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1",
        "secrets_loaded": bool(os.getenv("FOS_SECRETS_ARN")),
        "llm_provider": os.getenv("LLM_PROVIDER", "stub"),
        "bedrock_model_id": os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"),
    }
    logger.info(f"AWS Configuration: Region={config['region']}, Provider={config['llm_provider']}")
    return config
