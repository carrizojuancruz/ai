"""Tests for llm/client.py - LLM provider factory pattern."""

from unittest.mock import patch

from app.services.llm.bedrock import BedrockLLM
from app.services.llm.client import get_llm_client
from app.services.llm.stub import StubLLM


class TestGetLlmClient:
    """Test get_llm_client factory function."""

    @patch("app.services.llm.client.config")
    def test_returns_bedrock_when_provider_is_bedrock(self, mock_config):
        """Should return BedrockLLM instance when provider is 'bedrock'."""
        mock_config.LLM_PROVIDER = "bedrock"

        result = get_llm_client()

        assert isinstance(result, BedrockLLM)

    @patch("app.services.llm.client.config")
    def test_returns_stub_for_non_bedrock_providers(self, mock_config):
        """Should return StubLLM for any provider other than bedrock."""
        # Test stub provider
        mock_config.LLM_PROVIDER = "stub"
        assert isinstance(get_llm_client(), StubLLM)

        # Test empty string
        mock_config.LLM_PROVIDER = ""
        assert isinstance(get_llm_client(), StubLLM)

        # Test unknown provider
        mock_config.LLM_PROVIDER = "openai"
        assert isinstance(get_llm_client(), StubLLM)

    @patch("app.services.llm.client.config")
    def test_normalizes_provider_name(self, mock_config):
        """Should normalize provider name (strip whitespace and lowercase)."""
        # Test uppercase
        mock_config.LLM_PROVIDER = "BEDROCK"
        assert isinstance(get_llm_client(), BedrockLLM)

        # Test with whitespace
        mock_config.LLM_PROVIDER = "  bedrock  "
        assert isinstance(get_llm_client(), BedrockLLM)

        # Test mixed case with whitespace
        mock_config.LLM_PROVIDER = "  BeDrOcK  "
        assert isinstance(get_llm_client(), BedrockLLM)

    @patch("app.services.llm.client.config")
    @patch("app.services.llm.client.BedrockLLM")
    def test_falls_back_to_stub_on_initialization_error(
        self, mock_bedrock_class, mock_config
    ):
        """Should fall back to StubLLM if provider initialization fails."""
        mock_config.LLM_PROVIDER = "bedrock"
        mock_bedrock_class.side_effect = Exception("AWS credentials missing")

        result = get_llm_client()

        assert isinstance(result, StubLLM)
