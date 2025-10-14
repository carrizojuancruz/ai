"""Unit tests for guest agent."""

from unittest.mock import Mock, patch

import pytest

from app.agents.guest.agent import get_guest_graph


@pytest.fixture(autouse=True)
def clear_lru_cache():
    """Clear LRU cache before each test."""
    get_guest_graph.cache_clear()
    yield


class TestGetGuestGraph:
    """Tests for get_guest_graph function."""

    @patch('app.agents.guest.agent.create_react_agent')
    @patch('app.agents.guest.agent.ChatBedrock')
    @patch('app.agents.guest.agent.CallbackHandler')
    def test_get_guest_graph_successful_creation(self, mock_callback_handler, mock_chat_bedrock, mock_create_react, mock_config):
        """Test successful creation of guest graph with all dependencies, prompt content, and guardrails."""
        # Setup mocks
        mock_graph = Mock()
        mock_create_react.return_value = mock_graph
        mock_bedrock_instance = Mock()
        mock_chat_bedrock.return_value = mock_bedrock_instance
        mock_callback_instance = Mock()
        mock_callback_handler.return_value = mock_callback_instance

        # Call function
        result = get_guest_graph()

        # Assertions
        assert result == mock_graph

        # Verify ChatBedrock was created with correct parameters
        mock_chat_bedrock.assert_called_once()
        call_kwargs = mock_chat_bedrock.call_args[1]
        assert call_kwargs['model_id'] == 'anthropic.claude-3-sonnet-20240229-v1:0'
        assert call_kwargs['region_name'] == 'us-east-1'
        assert call_kwargs['streaming'] is True
        assert 'callbacks' in call_kwargs

        # Verify guardrails configuration
        expected_guardrails = {
            "guardrailIdentifier": 'test-guardrail-id',
            "guardrailVersion": '1',
            "trace": "enabled",
        }
        assert call_kwargs['guardrails'] == expected_guardrails

        # Verify create_react_agent was called with correct parameters
        mock_create_react.assert_called_once()
        call_args = mock_create_react.call_args
        assert call_args[1]['model'] == mock_bedrock_instance
        assert call_args[1]['tools'] == []
        assert call_args[1]['name'] == "guestAgent"

        # Verify prompt exists and is a non-empty string
        prompt = call_args[1]['prompt']
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    @patch('app.agents.guest.agent.create_react_agent')
    @patch('app.agents.guest.agent.ChatBedrock')
    @patch('app.agents.guest.agent.CallbackHandler')
    def test_get_guest_graph_without_langfuse_credentials(self, mock_callback_handler, mock_chat_bedrock, mock_create_react, mock_config):
        """Test guest graph creation when Langfuse credentials are missing."""
        # Setup config without Langfuse credentials
        with patch.object(mock_config, 'LANGFUSE_GUEST_PUBLIC_KEY', None), \
             patch.object(mock_config, 'LANGFUSE_GUEST_SECRET_KEY', None), \
             patch.object(mock_config, 'LANGFUSE_HOST', None):

            mock_graph = Mock()
            mock_create_react.return_value = mock_graph
            mock_bedrock_instance = Mock()
            mock_chat_bedrock.return_value = mock_bedrock_instance

            with patch('app.agents.guest.agent.logger'):
                result = get_guest_graph()

                # Verify result
                assert result == mock_graph

                # Verify ChatBedrock was created without callbacks
                mock_chat_bedrock.assert_called_once()
                call_kwargs = mock_chat_bedrock.call_args[1]
                assert call_kwargs['callbacks'] == []

    @patch('app.agents.guest.agent.create_react_agent')
    @patch('app.agents.guest.agent.ChatBedrock')
    @patch('app.agents.guest.agent.CallbackHandler')
    def test_get_guest_graph_langfuse_callback_exception(self, mock_callback_handler, mock_chat_bedrock, mock_create_react, mock_config):
        """Test guest graph creation when Langfuse callback initialization fails."""
        # Setup mocks
        mock_graph = Mock()
        mock_create_react.return_value = mock_graph
        mock_bedrock_instance = Mock()
        mock_chat_bedrock.return_value = mock_bedrock_instance

        # Make CallbackHandler raise exception
        mock_callback_handler.side_effect = Exception("Connection failed")

        with patch('app.agents.guest.agent.logger'):
            result = get_guest_graph()

            # Verify result despite exception
            assert result == mock_graph

            # Verify ChatBedrock was created without callbacks
            mock_chat_bedrock.assert_called_once()
            call_kwargs = mock_chat_bedrock.call_args[1]
            assert call_kwargs['callbacks'] == []

    @patch('app.agents.guest.agent.ChatBedrock')
    @patch('app.agents.guest.agent.CallbackHandler')
    @patch('app.agents.guest.agent.create_react_agent')
    def test_get_guest_graph_caching(self, mock_create_react, mock_callback_handler, mock_chat_bedrock, mock_config):
        """Test that get_guest_graph uses lru_cache for caching."""
        # Setup mocks
        mock_graph = Mock()
        mock_create_react.return_value = mock_graph
        mock_bedrock_instance = Mock()
        mock_chat_bedrock.return_value = mock_bedrock_instance
        mock_callback_instance = Mock()
        mock_callback_handler.return_value = mock_callback_instance

        # Call function twice
        result1 = get_guest_graph()
        result2 = get_guest_graph()

        # Verify create_react_agent was called only once (cached)
        assert mock_create_react.call_count == 1
        assert result1 == result2 == mock_graph

    @patch('app.agents.guest.agent.ChatBedrock')
    @patch('app.agents.guest.agent.CallbackHandler')
    @patch('app.agents.guest.agent.create_react_agent')
    def test_get_guest_graph_guardrails_configuration(self, mock_create_react, mock_callback_handler, mock_chat_bedrock, mock_config):
        """Test that guardrails are properly configured."""
        # Setup mocks
        mock_graph = Mock()
        mock_create_react.return_value = mock_graph
        mock_bedrock_instance = Mock()
        mock_chat_bedrock.return_value = mock_bedrock_instance
        mock_callback_instance = Mock()
        mock_callback_handler.return_value = mock_callback_instance

        # Call function
        get_guest_graph()

        # Verify ChatBedrock guardrails configuration
        call_kwargs = mock_chat_bedrock.call_args[1]
        expected_guardrails = {
            "guardrailIdentifier": 'test-guardrail-id',
            "guardrailVersion": '1',
            "trace": "enabled",
        }
        assert call_kwargs['guardrails'] == expected_guardrails
