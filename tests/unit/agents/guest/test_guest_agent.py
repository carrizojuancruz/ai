"""Unit tests for guest agent."""

from unittest.mock import Mock, patch

import pytest
from langgraph.graph import MessagesState

from app.agents.guest.agent import get_guest_graph


@pytest.fixture(autouse=True)
def clear_lru_cache():
    """Clear LRU cache before each test."""
    get_guest_graph.cache_clear()
    yield


class TestGetGuestGraph:
    """Tests for get_guest_graph function."""

    @patch("app.services.llm.prompt_loader.prompt_loader")
    @patch("app.agents.guest.agent.Langfuse")
    @patch("app.agents.guest.agent.StateGraph")
    @patch("app.agents.guest.agent.get_guest_checkpointer")
    @patch("app.agents.guest.agent.ChatBedrock")
    @patch("app.agents.guest.agent.CallbackHandler")
    def test_get_guest_graph_successful_creation(
        self,
        mock_callback_handler,
        mock_chat_bedrock,
        mock_get_guest_checkpointer,
        mock_state_graph,
        mock_langfuse,
        mock_prompt_loader,
        mock_config,
    ):
        """Test successful creation of guest graph with guardrails and checkpointer."""
        mock_graph = Mock()
        mock_builder = Mock()
        mock_state_graph.return_value = mock_builder
        mock_builder.compile.return_value = mock_graph
        mock_prompt_loader.load.return_value = "guest prompt"
        mock_bedrock_instance = Mock()
        mock_chat_bedrock.return_value = mock_bedrock_instance
        mock_callback_instance = Mock()
        mock_callback_handler.return_value = mock_callback_instance

        result = get_guest_graph()

        assert result == mock_graph
        mock_state_graph.assert_called_once_with(MessagesState)
        mock_builder.compile.assert_called_once_with(checkpointer=mock_get_guest_checkpointer.return_value)

        mock_chat_bedrock.assert_called_once()
        call_kwargs = mock_chat_bedrock.call_args[1]
        assert call_kwargs["model_id"] == "anthropic.claude-3-sonnet-20240229-v1:0"
        assert call_kwargs["region_name"] == "us-east-1"
        assert call_kwargs["streaming"] is True
        assert call_kwargs["guardrails"] == {
            "guardrailIdentifier": "test-guardrail-id",
            "guardrailVersion": "1",
            "trace": "enabled",
        }
        assert call_kwargs["callbacks"] == [mock_callback_instance]
        mock_langfuse.assert_called_once()

    @patch("app.services.llm.prompt_loader.prompt_loader")
    @patch("app.agents.guest.agent.Langfuse")
    @patch("app.agents.guest.agent.StateGraph")
    @patch("app.agents.guest.agent.get_guest_checkpointer")
    @patch("app.agents.guest.agent.ChatBedrock")
    @patch("app.agents.guest.agent.CallbackHandler")
    def test_get_guest_graph_without_langfuse_credentials(
        self,
        mock_callback_handler,
        mock_chat_bedrock,
        mock_get_guest_checkpointer,
        mock_state_graph,
        mock_langfuse,
        mock_prompt_loader,
        mock_config,
    ):
        """Test guest graph creation when Langfuse credentials are missing."""
        mock_graph = Mock()
        mock_builder = Mock()
        mock_state_graph.return_value = mock_builder
        mock_builder.compile.return_value = mock_graph
        mock_prompt_loader.load.return_value = "guest prompt"
        mock_chat_bedrock.return_value = Mock()

        with (
            patch.object(mock_config, "LANGFUSE_GUEST_PUBLIC_KEY", None),
            patch.object(mock_config, "LANGFUSE_GUEST_SECRET_KEY", None),
            patch.object(mock_config, "LANGFUSE_HOST", None),
            patch("app.agents.guest.agent.logger"),
        ):
            result = get_guest_graph()

        assert result == mock_graph
        call_kwargs = mock_chat_bedrock.call_args[1]
        assert call_kwargs["callbacks"] == []
        mock_langfuse.assert_not_called()

    @patch("app.services.llm.prompt_loader.prompt_loader")
    @patch("app.agents.guest.agent.Langfuse")
    @patch("app.agents.guest.agent.StateGraph")
    @patch("app.agents.guest.agent.get_guest_checkpointer")
    @patch("app.agents.guest.agent.ChatBedrock")
    @patch("app.agents.guest.agent.CallbackHandler")
    def test_get_guest_graph_langfuse_callback_exception(
        self,
        mock_callback_handler,
        mock_chat_bedrock,
        mock_get_guest_checkpointer,
        mock_state_graph,
        mock_langfuse,
        mock_prompt_loader,
        mock_config,
    ):
        """Test guest graph creation when Langfuse callback initialization fails."""
        mock_graph = Mock()
        mock_builder = Mock()
        mock_state_graph.return_value = mock_builder
        mock_builder.compile.return_value = mock_graph
        mock_prompt_loader.load.return_value = "guest prompt"
        mock_chat_bedrock.return_value = Mock()
        mock_callback_handler.side_effect = Exception("Connection failed")

        with patch("app.agents.guest.agent.logger"):
            result = get_guest_graph()

        assert result == mock_graph
        call_kwargs = mock_chat_bedrock.call_args[1]
        assert call_kwargs["callbacks"] == []

    @patch("app.services.llm.prompt_loader.prompt_loader")
    @patch("app.agents.guest.agent.Langfuse")
    @patch("app.agents.guest.agent.StateGraph")
    @patch("app.agents.guest.agent.get_guest_checkpointer")
    @patch("app.agents.guest.agent.ChatBedrock")
    @patch("app.agents.guest.agent.CallbackHandler")
    def test_get_guest_graph_caching(
        self,
        mock_callback_handler,
        mock_chat_bedrock,
        mock_get_guest_checkpointer,
        mock_state_graph,
        mock_langfuse,
        mock_prompt_loader,
        mock_config,
    ):
        """Test that get_guest_graph uses lru_cache for caching."""
        mock_graph = Mock()
        mock_builder = Mock()
        mock_state_graph.return_value = mock_builder
        mock_builder.compile.return_value = mock_graph
        mock_prompt_loader.load.return_value = "guest prompt"
        mock_chat_bedrock.return_value = Mock()

        result1 = get_guest_graph()
        result2 = get_guest_graph()

        assert result1 == result2 == mock_graph
        assert mock_state_graph.call_count == 1
        mock_builder.compile.assert_called_once()

    @patch("app.services.llm.prompt_loader.prompt_loader")
    @patch("app.agents.guest.agent.Langfuse")
    @patch("app.agents.guest.agent.StateGraph")
    @patch("app.agents.guest.agent.get_guest_checkpointer")
    @patch("app.agents.guest.agent.ChatBedrock")
    @patch("app.agents.guest.agent.CallbackHandler")
    def test_get_guest_graph_guardrails_configuration(
        self,
        mock_callback_handler,
        mock_chat_bedrock,
        mock_get_guest_checkpointer,
        mock_state_graph,
        mock_langfuse,
        mock_prompt_loader,
        mock_config,
    ):
        """Test that guardrails are properly configured."""
        mock_graph = Mock()
        mock_builder = Mock()
        mock_state_graph.return_value = mock_builder
        mock_builder.compile.return_value = mock_graph
        mock_prompt_loader.load.return_value = "guest prompt"
        mock_chat_bedrock.return_value = Mock()

        get_guest_graph()

        call_kwargs = mock_chat_bedrock.call_args[1]
        expected_guardrails = {
            "guardrailIdentifier": "test-guardrail-id",
            "guardrailVersion": "1",
            "trace": "enabled",
        }
        assert call_kwargs["guardrails"] == expected_guardrails
