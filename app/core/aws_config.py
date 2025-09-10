from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)

class AWSConfig:
    """AWSConfig class for managing AWS configuration and secrets."""

    def __init__(self, region: str, secrets_arn: str):
        self.session = boto3.session.Session()
        self.region = region
        self.secrets_arn = secrets_arn

    def get_secrets_manager_values(self) -> dict[str, Any]:
        """Get secrets from AWS Secrets Manager."""
        if not self.secrets_arn:
            logger.info("No FOS_SECRETS_ID provided, using local environment variables")
            return
        secret_data = {}
        try:
            client = self.session.client(service_name="secretsmanager", region_name=self.region)
            response = client.get_secret_value(SecretId=self.secrets_arn)
            if "SecretString" in response:
                secret_string = response["SecretString"]
                secret_data = json.loads(secret_string)
                logger.info("Successfully loaded %d secrets from AWS Secrets Manager", len(secret_data))

                # Check if AURORA_SECRET_ARN is in the secrets
                if "AURORA_SECRET_ARN" in secret_data:
                    aurora_secret_arn = secret_data["AURORA_SECRET_ARN"]
                    logger.info("Found AURORA_SECRET_ARN, fetching database credentials")

                    # Fetch the Aurora secret
                    aurora_credentials = self._fetch_aurora_credentials(client, aurora_secret_arn)
                    if aurora_credentials:
                        # Add database credentials to secret_data
                        secret_data["DATABASE_USER"] = aurora_credentials.get("username")
                        secret_data["DATABASE_PASSWORD"] = aurora_credentials.get("password")
                        logger.info("Successfully loaded database credentials from Aurora secret")
            else:
                logger.error("Secret does not contain a SecretString")
        except ClientError as e:
            logger.error("Error retrieving secret: %s", e)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse secret JSON: %s", e)
        return secret_data

    def _fetch_aurora_credentials(self, client, aurora_secret_arn: str) -> dict[str, Any]:
        """Fetch Aurora database credentials from the provided secret ARN."""
        try:
            response = client.get_secret_value(SecretId=aurora_secret_arn)
            if "SecretString" in response:
                secret_string = response["SecretString"]
                aurora_secret = json.loads(secret_string)
                logger.debug("Successfully fetched Aurora credentials")
                return aurora_secret
            else:
                logger.error("Aurora secret does not contain a SecretString")
                return {}
        except ClientError as e:
            logger.error("Error retrieving Aurora secret: %s", e)
            return {}
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Aurora secret JSON: %s", e)
            return {}

def load_aws_secrets() -> None:
    """Load AWS secrets from AWS Secrets Manager."""
    secret_id = os.getenv("FOS_SECRETS_ID")
    if not secret_id:
        logger.info("No FOS_SECRETS_ID provided, using local environment variables")
        return

    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")

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

        # Check if AURORA_SECRET_ARN is in the secrets
        if "AURORA_SECRET_ARN" in secret_data:
            aurora_secret_arn = secret_data["AURORA_SECRET_ARN"]
            logger.info("Found AURORA_SECRET_ARN, fetching database credentials")

            try:
                # Fetch the Aurora secret
                aurora_response = client.get_secret_value(SecretId=aurora_secret_arn)
                if "SecretString" in aurora_response:
                    aurora_secret = json.loads(aurora_response["SecretString"])
                    # Add database credentials to secret_data
                    secret_data["DATABASE_USER"] = aurora_secret.get("username")
                    secret_data["DATABASE_PASSWORD"] = aurora_secret.get("password")
                    logger.info("Successfully loaded database credentials from Aurora secret")
            except ClientError as e:
                logger.error(f"Error retrieving Aurora secret: {e}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Aurora secret JSON: {e}")

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
        "region": os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"),
        "secrets_loaded": bool(os.getenv("FOS_SECRETS_ID")),
        "llm_provider": os.getenv("LLM_PROVIDER"),
        "bedrock_model_id": os.getenv("BEDROCK_MODEL_ID"),
    }
    logger.info(f"AWS Configuration: Region={aws_config['region']}, Provider={aws_config['llm_provider']}")
    return aws_config
