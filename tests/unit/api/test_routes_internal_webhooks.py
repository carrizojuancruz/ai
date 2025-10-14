from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.routes_internal_webhooks import _audit_config_configuration, get_secrets_status, update_secrets


class TestAuditConfigConfiguration:
    @patch("app.api.routes_internal_webhooks.config")
    def test_returns_audit_structure(self, mock_config):
        mock_config.AWS_REGION = "us-east-1"
        mock_config.DATABASE_HOST = "localhost"
        mock_config.LLM_PROVIDER = "bedrock"
        mock_config.MEMORY_MERGE_TOPK = 5

        mock_attrs = ["AWS_REGION", "DATABASE_HOST", "LLM_PROVIDER", "MEMORY_MERGE_TOPK"]
        with patch("builtins.dir", return_value=mock_attrs):
            result = _audit_config_configuration()

        assert "memory_config" in result
        assert "aws_config" in result
        assert "summary" in result

    @patch("app.api.routes_internal_webhooks.config")
    def test_masks_sensitive_fields(self, mock_config):
        mock_config.AWS_SECRET_ACCESS_KEY = "secret123"
        mock_config.DATABASE_PASSWORD = "dbpass"

        result = _audit_config_configuration()

        assert result["aws_config"]["AWS_SECRET_ACCESS_KEY"]["value"] == "***"


class TestUpdateSecrets:
    @pytest.mark.asyncio
    @patch("app.api.routes_internal_webhooks.config")
    @patch("app.api.routes_internal_webhooks._reload_dependent_services")
    @patch("app.api.routes_internal_webhooks.AWSConfig")
    async def test_updates_secrets_successfully(self, mock_aws_config, mock_reload, mock_config):
        mock_config.FOS_SECRETS_ID = "test-secret"
        mock_config.AWS_REGION = "us-east-1"
        mock_config.reload_config.return_value = True

        mock_aws_instance = MagicMock()
        mock_aws_instance.get_secrets_manager_values.return_value = {"KEY1": "value1", "KEY2": "value2"}
        mock_aws_config.return_value = mock_aws_instance
        mock_reload.return_value = {"aws_clients": True}

        result = await update_secrets()

        assert result.success is True
        assert result.secrets_loaded == 2

    @pytest.mark.asyncio
    @patch("app.api.routes_internal_webhooks.config")
    async def test_handles_missing_secrets_id(self, mock_config):
        mock_config.FOS_SECRETS_ID = None
        mock_config.AWS_REGION = "us-east-1"

        result = await update_secrets()

        assert result.success is False

    @pytest.mark.asyncio
    @patch("app.api.routes_internal_webhooks.config")
    @patch("app.api.routes_internal_webhooks.AWSConfig")
    async def test_handles_aws_error(self, mock_aws_config, mock_config):
        mock_config.FOS_SECRETS_ID = "test-secret"
        mock_config.AWS_REGION = "us-east-1"
        mock_aws_config.side_effect = ValueError("AWS error")

        with pytest.raises(HTTPException):
            await update_secrets()


class TestGetSecretsStatus:
    @pytest.mark.asyncio
    @patch("app.api.routes_internal_webhooks.config")
    @patch("app.api.routes_internal_webhooks._audit_config_configuration")
    async def test_returns_status_info(self, mock_audit, mock_config):
        mock_config.FOS_SECRETS_ID = None
        mock_config.AWS_REGION = "us-east-1"
        mock_config.ENVIRONMENT = "test"
        mock_config.DEBUG = False
        mock_audit.return_value = {"summary": {"total_configured": 50, "total_missing": 10, "critical_missing": [], "optional_missing": []}}

        result = await get_secrets_status()

        assert "aws_region" in result
        assert result["fos_secrets_id_configured"] is False

    @pytest.mark.asyncio
    @patch("app.api.routes_internal_webhooks.config")
    @patch("app.api.routes_internal_webhooks._audit_config_configuration")
    async def test_handles_error(self, mock_audit, mock_config):
        mock_audit.side_effect = RuntimeError("Error")

        with pytest.raises(HTTPException):
            await get_secrets_status()

