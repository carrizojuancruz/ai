from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)

AURORA_SECRET_ARN_KEY = "AURORA_SECRET_ARN"
FOS_AI_SECRET_ARN_KEY = "FOS_AI_SECRET_ARN"
REDIS_SECRET_ARN_KEY = "REDIS_SECRET_ARN"
DATABASE_USER_KEY = "DATABASE_USER"
DATABASE_PASSWORD_KEY = "DATABASE_PASSWORD"


class AWSConfig:
    """Manages AWS Secrets Manager configuration."""

    def __init__(self, region: str, secrets_arn: str):
        self.session = boto3.session.Session()
        self.region = region
        self.secrets_arn = secrets_arn

    def get_secrets_manager_values(self) -> dict[str, Any]:
        if not self.secrets_arn:
            logger.info("No FOS_SECRETS_ID provided, using local environment variables")
            return {}
        client = self._setup_aws_client()
        secret_data = self._fetch_secret(client, self.secrets_arn, "main")
        if secret_data:
            secret_data = self._process_nested_secrets(client, secret_data)
        return secret_data

    def _setup_aws_client(self):
        return self.session.client(service_name="secretsmanager", region_name=self.region)

    def _fetch_secret(self, client, secret_arn: str, secret_name: str) -> dict[str, Any]:
        try:
            response = client.get_secret_value(SecretId=secret_arn)
            if "SecretString" not in response:
                logger.error("%s secret is missing SecretString", secret_name)
                return {}
            secret_data = json.loads(response["SecretString"])
            logger.info("Loaded %s secret with %d variables", secret_name, len(secret_data))
            return secret_data
        except ClientError as e:
            logger.error("Error retrieving %s secret: %s", secret_name, e)
            return {}
        except json.JSONDecodeError as e:
            logger.error("Failed to parse %s secret JSON: %s", secret_name, e)
            return {}

    def _process_nested_secrets(self, client, secret_data: dict[str, Any]) -> dict[str, Any]:
        if AURORA_SECRET_ARN_KEY in secret_data:
            aurora_credentials = self._fetch_secret(client, secret_data[AURORA_SECRET_ARN_KEY], "Aurora")
            if aurora_credentials:
                secret_data[DATABASE_USER_KEY] = aurora_credentials.get("username")
                secret_data[DATABASE_PASSWORD_KEY] = aurora_credentials.get("password")
                logger.info("Mapped Aurora credentials to database variables")
        if FOS_AI_SECRET_ARN_KEY in secret_data:
            fos_ai_secret = self._fetch_secret(client, secret_data[FOS_AI_SECRET_ARN_KEY], "FOS_AI")
            if fos_ai_secret:
                secret_data.update(fos_ai_secret)
                logger.info("Applied FOS_AI secret variables")
        if REDIS_SECRET_ARN_KEY in secret_data:
            redis_secret = self._fetch_secret(client, secret_data[REDIS_SECRET_ARN_KEY], "Redis")
            if redis_secret:
                keys = [
                    "REDIS_USERNAME",
                    "REDIS_PASSWORD",
                    "REDIS_HOST",
                    "REDIS_ENDPOINT",
                    "REDIS_PORT",
                    "REDIS_ACCESS_STRING",
                    "REDIS_TLS",
                    "REDIS_TTL_DEFAULT",
                    "REDIS_TTL_SESSION",
                    "REDIS_TTL_SSE",
                ]
                mapped: dict[str, Any] = {}
                for key in keys:
                    if key in redis_secret and redis_secret[key] is not None:
                        mapped[key] = redis_secret[key]
                if "REDIS_USERNAME" not in mapped and "username" in redis_secret:
                    mapped["REDIS_USERNAME"] = redis_secret["username"]
                if "REDIS_PASSWORD" not in mapped and "password" in redis_secret:
                    mapped["REDIS_PASSWORD"] = redis_secret["password"]
                if "REDIS_HOST" not in mapped:
                    endpoint = redis_secret.get("REDIS_ENDPOINT") or redis_secret.get("endpoint")
                    if endpoint:
                        mapped["REDIS_HOST"] = endpoint
                if "REDIS_PORT" not in mapped and "port" in redis_secret:
                    mapped["REDIS_PORT"] = str(redis_secret["port"]) if redis_secret["port"] is not None else None
                secret_data.update({k: v for k, v in mapped.items() if v is not None})
                logger.info("Applied Redis secret variables: %s", ", ".join(sorted(mapped.keys())))
        return secret_data


def load_aws_secrets() -> None:
    secret_id = os.getenv("FOS_SECRETS_ID")
    if not secret_id:
        logger.info("No FOS_SECRETS_ID provided, using local environment variables")
        return
    region = _get_aws_region()
    try:
        aws_config = AWSConfig(region=region, secrets_arn=secret_id)
        secret_data = aws_config.get_secrets_manager_values()
        if secret_data:
            _apply_secrets_to_environment(secret_data)
    except NoCredentialsError:
        logger.warning("AWS credentials not found, skipping Secrets Manager loading")
    except ClientError as e:
        _handle_client_error(e, secret_id)
    except Exception as e:
        logger.error("Unexpected error loading secrets: %s", e)


def _get_aws_region() -> str:
    return os.getenv("AWS_REGION")


def _apply_secrets_to_environment(secret_data: dict[str, Any], region: str | None = None) -> None:
    loaded_count = 0
    for key, value in secret_data.items():
        os.environ[key] = str(value)
        logger.debug("Set environment variable: %s", key)
        loaded_count += 1
    logger.info("Loaded %d secrets from AWS Secrets Manager", loaded_count)


def _handle_client_error(error: ClientError, secret_id: str) -> None:
    error_code = error.response["Error"]["Code"]
    if error_code == "ResourceNotFoundException":
        logger.error("Secret %s not found", secret_id)
    elif error_code == "AccessDeniedException":
        logger.error("Access denied to secret %s", secret_id)
    else:
        logger.error("Error retrieving secret: %s", error)


def configure_aws_environment() -> dict[str, Any]:
    aws_config = {
        "region": os.getenv("AWS_REGION"),
        "secrets_loaded": bool(os.getenv("FOS_SECRETS_ID")),
    }
    logger.info(f"AWS Configuration: Region={aws_config['region']}")
    return aws_config
