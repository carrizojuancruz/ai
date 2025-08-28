from __future__ import annotations

import json
import logging
import os
from typing import Any

from app.core.config import config

logger = logging.getLogger(__name__)


def load_aws_secrets() -> None:
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
    except ImportError:
        logger.warning("boto3 not available, skipping AWS Secrets Manager loading")
        return

    secret_id = config.FOS_SECRETS_ID
    if not secret_id:
        logger.info("No FOS_SECRETS_ID provided, using local environment variables")
        return

    region = config.get_aws_region()

    try:
        session = boto3.session.Session()
        client = session.client(service_name="secretsmanager", region_name=region)
        logger.info(f"Loading secrets from AWS Secrets Manager: {secret_id}")
        response = client.get_secret_value(SecretId=secret_id)
        if "SecretString" in response:
            secret_string = response["SecretString"]
        else:
            logger.error("Binary secrets are not supported")
            return
        secret_data = json.loads(secret_string)
        loaded_count = 0
        for key, value in secret_data.items():
            os.environ[key] = str(value)
            logger.debug(f"Set environment variable: {key} (overwritten if existed)")
            loaded_count += 1
        logger.info(f"Successfully loaded {loaded_count} secrets from AWS Secrets Manager")
        if "AWS_REGION" not in os.environ and "AWS_DEFAULT_REGION" not in os.environ:
            os.environ["AWS_DEFAULT_REGION"] = region
            logger.info(f"Set AWS_DEFAULT_REGION to {region}")
    except NoCredentialsError:
        logger.warning("AWS credentials not found, skipping Secrets Manager loading")
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ResourceNotFoundException":
            logger.error(f"Secret {secret_id} not found")
        elif error_code == "AccessDeniedException":
            logger.error(f"Access denied to secret {secret_id}")
        else:
            logger.error(f"Error retrieving secret: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse secret JSON: {e}")
    except Exception as e:
        logger.error(f"Unexpected error loading secrets: {e}")


def configure_aws_environment() -> dict[str, Any]:
    aws_config = {
        "region": config.get_aws_region(),
        "secrets_loaded": bool(config.FOS_SECRETS_ID),
        "llm_provider": config.LLM_PROVIDER,
        "bedrock_model_id": config.BEDROCK_MODEL_ID,
    }
    logger.info(f"AWS Configuration: Region={aws_config['region']}, Provider={aws_config['llm_provider']}")
    return aws_config
