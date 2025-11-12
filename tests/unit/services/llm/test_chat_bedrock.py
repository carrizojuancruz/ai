"""Tests for ChatBedrock wrapper with retry logic."""
from unittest.mock import patch

import pytest
from botocore.exceptions import ClientError

from app.services.llm.chat_bedrock import (
    ChatBedrock,
    _is_retryable_validation_error,
)


class TestIsRetryableValidationError:
    """Test the retry condition logic."""

    def test_returns_false_for_non_client_error(self):
        """Should not retry on non-ClientError exceptions."""
        assert not _is_retryable_validation_error(ValueError("test"))
        assert not _is_retryable_validation_error(Exception("test"))

    def test_returns_false_for_authentication_error(self):
        """Should not retry on authentication failures."""
        error = ClientError(
            {
                "Error": {
                    "Code": "UnrecognizedClientException",
                    "Message": "The security token included in the request is invalid."
                }
            },
            "Converse"
        )
        assert not _is_retryable_validation_error(error)

    def test_returns_false_for_invalid_model_error(self):
        """Should not retry on invalid model ID errors."""
        error = ClientError(
            {
                "Error": {
                    "Code": "ValidationException",
                    "Message": "The provided model identifier is invalid."
                }
            },
            "Converse"
        )
        assert not _is_retryable_validation_error(error)

    def test_returns_false_for_throttling_error(self):
        """Should not retry on throttling (handled by AWS SDK)."""
        error = ClientError(
            {
                "Error": {
                    "Code": "ThrottlingException",
                    "Message": "Rate exceeded"
                }
            },
            "Converse"
        )
        assert not _is_retryable_validation_error(error)

    def test_returns_true_for_validation_error_with_code(self):
        """Should retry on ValidationException with validation_error code."""
        error = ClientError(
            {
                "Error": {
                    "Code": "ValidationException",
                    "Message": 'The model returned the following errors: {"code":"validation_error","message":"ErrorEvent { error: APIError { type: \\"BadRequestError\\", code: Some(400), message: \\"Unexpected token 200012 while expecting start token 200006\\" } }"}'
                }
            },
            "Converse"
        )
        assert _is_retryable_validation_error(error)

    def test_returns_false_for_other_validation_errors(self):
        """Should not retry on other ValidationException errors."""
        error = ClientError(
            {
                "Error": {
                    "Code": "ValidationException",
                    "Message": "Invalid request parameters"
                }
            },
            "Converse"
        )
        assert not _is_retryable_validation_error(error)


class TestChatBedrockRetry:
    """Test ChatBedrock retry behavior."""

    @patch("app.services.llm.chat_bedrock.ChatBedrockConverse.invoke")
    def test_invoke_retries_on_validation_error(self, mock_invoke):
        """Should retry invoke() on transient ValidationException."""
        # First call fails with validation_error, second succeeds
        mock_invoke.side_effect = [
            ClientError(
                {
                    "Error": {
                        "Code": "ValidationException",
                        "Message": '{"code":"validation_error","message":"Transient error"}'
                    }
                },
                "Converse"
            ),
            {"content": "success"}
        ]

        chat = ChatBedrock(model_id="test-model", region_name="us-east-1")
        result = chat.invoke("test")

        assert result == {"content": "success"}
        assert mock_invoke.call_count == 2

    @patch("app.services.llm.chat_bedrock.ChatBedrockConverse.invoke")
    def test_invoke_does_not_retry_on_auth_error(self, mock_invoke):
        """Should not retry invoke() on authentication errors."""
        mock_invoke.side_effect = ClientError(
            {
                "Error": {
                    "Code": "UnrecognizedClientException",
                    "Message": "Invalid token"
                }
            },
            "Converse"
        )

        chat = ChatBedrock(model_id="test-model", region_name="us-east-1")

        with pytest.raises(ClientError):
            chat.invoke("test")

        # Should only call once, no retry
        assert mock_invoke.call_count == 1

    @patch("app.services.llm.chat_bedrock.ChatBedrockConverse.ainvoke")
    @pytest.mark.asyncio
    async def test_ainvoke_retries_on_validation_error(self, mock_ainvoke):
        """Should retry ainvoke() on transient ValidationException."""
        # First call fails with validation_error, second succeeds
        call_counter = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_counter
            call_counter += 1
            if call_counter == 1:
                raise ClientError(
                    {
                        "Error": {
                            "Code": "ValidationException",
                            "Message": '{"code":"validation_error","message":"Transient error"}'
                        }
                    },
                    "Converse"
                )
            return {"content": "success"}

        mock_ainvoke.side_effect = side_effect

        chat = ChatBedrock(model_id="test-model", region_name="us-east-1")
        result = await chat.ainvoke("test")

        assert result == {"content": "success"}
        assert mock_ainvoke.call_count == 2
