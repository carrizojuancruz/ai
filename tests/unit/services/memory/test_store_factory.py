"""Tests for memory/store_factory.py factory function."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.memory.store_factory import create_s3_vectors_store_from_env


class TestCreateS3VectorsStoreFromEnv:
    """Test S3VectorsStore factory function."""

    @patch("app.services.memory.store_factory.boto3")
    @patch("app.services.memory.store_factory.config")
    def test_create_store_with_all_params(self, mock_config, mock_boto3):
        """Test successful store creation with all parameters."""
        # Setup
        mock_config.S3V_BUCKET = "test-bucket"
        mock_config.S3V_INDEX_MEMORY = "memory-index"
        mock_config.get_aws_region.return_value = "us-east-1"
        mock_config.S3V_DISTANCE = "cosine"
        mock_config.S3V_DIMS = 1024
        mock_config.BEDROCK_EMBED_MODEL_ID = "amazon.titan-embed-text-v1"

        mock_s3v_client = MagicMock()
        mock_bedrock_client = MagicMock()
        mock_boto3.client.side_effect = [mock_s3v_client, mock_bedrock_client]

        # Execute
        result = create_s3_vectors_store_from_env()

        # Assert
        assert result is not None
        mock_boto3.client.assert_any_call("s3vectors", region_name="us-east-1")
        mock_boto3.client.assert_any_call("bedrock-runtime", region_name="us-east-1")
        assert mock_boto3.client.call_count == 2

    @patch("app.services.memory.store_factory.boto3")
    @patch("app.services.memory.store_factory.config")
    def test_validates_required_config(self, mock_config, mock_boto3):
        """Test validation of required configuration values."""
        invalid_cases = [
            (None, "memory-index"),  # Missing bucket
            ("test-bucket", None),    # Missing index
            ("", "memory-index"),     # Empty bucket
            ("test-bucket", ""),      # Empty index
        ]

        for bucket, index in invalid_cases:
            mock_config.S3V_BUCKET = bucket
            mock_config.S3V_INDEX_MEMORY = index

            with pytest.raises(RuntimeError, match="Missing S3V_BUCKET or S3V_INDEX_MEMORY"):
                create_s3_vectors_store_from_env()

    @patch("app.services.memory.store_factory.boto3")
    @patch("app.services.memory.store_factory.config")
    def test_region_fallback_logic(self, mock_config, mock_boto3):
        """Test region selection: custom > config region."""
        # Setup
        mock_config.S3V_BUCKET = "test-bucket"
        mock_config.S3V_INDEX_MEMORY = "memory-index"
        mock_config.get_aws_region.return_value = "us-east-1"
        mock_config.S3V_DISTANCE = "cosine"
        mock_config.S3V_DIMS = 1024
        mock_config.BEDROCK_EMBED_MODEL_ID = "model-id"

        mock_boto3.client.return_value = MagicMock()

        # Test 1: No custom region - should use config
        create_s3_vectors_store_from_env()
        mock_config.get_aws_region.assert_called_once()

        # Reset
        mock_config.get_aws_region.reset_mock()

        # Test 2: Custom region provided - should not call config
        create_s3_vectors_store_from_env(region_name="ap-south-1")
        mock_config.get_aws_region.assert_not_called()
