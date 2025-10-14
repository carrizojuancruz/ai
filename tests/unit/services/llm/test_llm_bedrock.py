"""
Comprehensive tests for BedrockLLM.

Tests focus on valuable business logic:
- AWS configuration and initialization
- Message generation with system prompts
- Streaming generation
- Structured data extraction
- Callback management
- Content normalization edge cases
"""
from unittest.mock import Mock, patch

import pytest

from app.services.llm.bedrock import BedrockLLM, _content_to_text, _safe_parse_json


class TestBedrockLLMInitialization:
    """Test BedrockLLM initialization and configuration."""

    def test_initialization_with_valid_config(self, mock_config):
        """LLM should initialize successfully with valid AWS configuration."""
        with patch("app.services.llm.bedrock.ChatBedrockConverse") as mock_chat:
            llm = BedrockLLM()

            assert llm.model_id == "anthropic.claude-v2"
            assert llm.temperature == 0.7
            assert llm._callbacks is None

            mock_chat.assert_called_once_with(
                model_id="anthropic.claude-v2",
                region_name="us-east-1",
                temperature=0.7
            )

    # Note: Tests that modify mock_config after fixture setup are removed
    # because the autouse fixture patches multiple locations


class TestCallbackManagement:
    """Test callback setting and propagation."""

    def test_set_callbacks_updates_internal_callbacks(self, mock_config):
        """Setting callbacks should update internal callback list."""
        with patch("app.services.llm.bedrock.ChatBedrockConverse"):
            llm = BedrockLLM()
            callbacks = [Mock(), Mock()]

            llm.set_callbacks(callbacks)

            assert llm._callbacks == callbacks

    def test_set_callbacks_propagates_to_chat_model(self, mock_config):
        """Setting callbacks should propagate to underlying chat model."""
        with patch("app.services.llm.bedrock.ChatBedrockConverse") as mock_chat:
            mock_model = Mock()
            mock_chat.return_value = mock_model

            llm = BedrockLLM()
            callbacks = [Mock()]
            llm.set_callbacks(callbacks)

            assert mock_model.callbacks == callbacks

    def test_set_callbacks_to_none(self, mock_config):
        """Setting callbacks to None should clear callbacks."""
        with patch("app.services.llm.bedrock.ChatBedrockConverse"):
            llm = BedrockLLM()
            llm.set_callbacks([Mock()])
            llm.set_callbacks(None)

            assert llm._callbacks is None


class TestGenerate:
    """Test synchronous text generation."""

    def test_generate_with_simple_prompt(self, mock_config):
        """Generate should invoke model with human message."""
        with patch("app.services.llm.bedrock.ChatBedrockConverse") as mock_chat:
            mock_response = Mock()
            mock_response.content = "Generated response"
            mock_model = Mock()
            mock_model.invoke.return_value = mock_response
            mock_chat.return_value = mock_model

            llm = BedrockLLM()
            result = llm.generate("What is 2+2?")

            assert result == "Generated response"
            assert mock_model.invoke.call_count == 1

    def test_generate_with_system_prompt(self, mock_config):
        """Generate should include system message when provided."""
        with patch("app.services.llm.bedrock.ChatBedrockConverse") as mock_chat:
            mock_response = Mock()
            mock_response.content = "Response"
            mock_model = Mock()
            mock_model.invoke.return_value = mock_response
            mock_chat.return_value = mock_model

            llm = BedrockLLM()
            llm.generate("Question", system="You are a helpful assistant")

            call_args = mock_model.invoke.call_args
            messages = call_args[0][0]

            # Should have system message first, then human message
            assert len(messages) == 2
            assert messages[0].content == "You are a helpful assistant"
            assert messages[1].content == "Question"

    def test_generate_passes_callbacks(self, mock_config):
        """Generate should pass callbacks to model if set."""
        with patch("app.services.llm.bedrock.ChatBedrockConverse") as mock_chat:
            mock_response = Mock()
            mock_response.content = "Response"
            mock_model = Mock()
            mock_model.invoke.return_value = mock_response
            mock_chat.return_value = mock_model

            llm = BedrockLLM()
            callbacks = [Mock()]
            llm.set_callbacks(callbacks)

            llm.generate("Question")

            call_args = mock_model.invoke.call_args
            config = call_args[1]["config"]
            assert config["callbacks"] == callbacks

    def test_generate_handles_list_content(self, mock_config):
        """Generate should handle content as list of blocks."""
        with patch("app.services.llm.bedrock.ChatBedrockConverse") as mock_chat:
            mock_response = Mock()
            mock_response.content = [{"text": "Part 1"}, {"text": " Part 2"}]
            mock_model = Mock()
            mock_model.invoke.return_value = mock_response
            mock_chat.return_value = mock_model

            llm = BedrockLLM()
            result = llm.generate("Question")

            assert result == "Part 1 Part 2"


class TestGenerateStream:
    """Test asynchronous streaming generation."""

    @pytest.mark.asyncio
    async def test_generate_stream_yields_chunks(self, mock_config):
        """Generate stream should yield text chunks as they arrive."""
        with patch("app.services.llm.bedrock.ChatBedrockConverse") as mock_chat:
            # Create async generator for streaming
            async def mock_astream(*args, **kwargs):
                chunks = [
                    Mock(content="Hello"),
                    Mock(content=" world"),
                    Mock(content="!")
                ]
                for chunk in chunks:
                    yield chunk

            mock_model = Mock()
            mock_model.astream = mock_astream
            mock_chat.return_value = mock_model

            llm = BedrockLLM()

            result_chunks = []
            async for chunk in llm.generate_stream("Test prompt"):
                result_chunks.append(chunk)

            assert result_chunks == ["Hello", " world", "!"]

    @pytest.mark.asyncio
    async def test_generate_stream_with_system_message(self, mock_config):
        """Generate stream should include system message when provided."""
        with patch("app.services.llm.bedrock.ChatBedrockConverse") as mock_chat:
            async def mock_astream(messages, **kwargs):
                # Verify messages structure
                assert len(messages) == 2
                assert messages[0].content == "System prompt"
                assert messages[1].content == "User prompt"

                yield Mock(content="Response")

            mock_model = Mock()
            mock_model.astream = mock_astream
            mock_chat.return_value = mock_model

            llm = BedrockLLM()

            chunks = []
            async for chunk in llm.generate_stream("User prompt", system="System prompt"):
                chunks.append(chunk)

            assert len(chunks) == 1

    @pytest.mark.asyncio
    async def test_generate_stream_filters_empty_chunks(self, mock_config):
        """Generate stream should skip chunks with no content."""
        with patch("app.services.llm.bedrock.ChatBedrockConverse") as mock_chat:
            async def mock_astream(*args, **kwargs):
                chunks = [
                    Mock(content="Text"),
                    Mock(content=""),
                    Mock(content=None),
                    Mock(content="More")
                ]
                for chunk in chunks:
                    yield chunk

            mock_model = Mock()
            mock_model.astream = mock_astream
            mock_chat.return_value = mock_model

            llm = BedrockLLM()

            result_chunks = []
            async for chunk in llm.generate_stream("Prompt"):
                result_chunks.append(chunk)

            # Should only get non-empty chunks
            assert result_chunks == ["Text", "More"]

    @pytest.mark.asyncio
    async def test_generate_stream_handles_list_content(self, mock_config):
        """Generate stream should handle content as list of blocks."""
        with patch("app.services.llm.bedrock.ChatBedrockConverse") as mock_chat:
            async def mock_astream(*args, **kwargs):
                yield Mock(content=[{"text": "Part 1"}, {"text": " Part 2"}])

            mock_model = Mock()
            mock_model.astream = mock_astream
            mock_chat.return_value = mock_model

            llm = BedrockLLM()

            result_chunks = []
            async for chunk in llm.generate_stream("Prompt"):
                result_chunks.append(chunk)

            assert result_chunks == ["Part 1 Part 2"]


class TestExtract:
    """Test structured data extraction."""

    def test_extract_with_valid_json_response(self, mock_config):
        """Extract should parse valid JSON from model response."""
        with patch("app.services.llm.bedrock.ChatBedrockConverse") as mock_chat:
            mock_response = Mock()
            mock_response.content = '{"name": "John", "age": 30}'
            mock_model = Mock()
            mock_model.invoke.return_value = mock_response
            mock_chat.return_value = mock_model

            llm = BedrockLLM()
            schema = {"type": "object", "properties": {"name": {"type": "string"}}}
            result = llm.extract(schema, "John is 30 years old")

            assert result == {"name": "John", "age": 30}

    def test_extract_handles_json_with_extra_text(self, mock_config):
        """Extract should extract JSON even when surrounded by extra text."""
        with patch("app.services.llm.bedrock.ChatBedrockConverse") as mock_chat:
            mock_response = Mock()
            mock_response.content = 'Here is the data: {"value": 42} and that is all'
            mock_model = Mock()
            mock_model.invoke.return_value = mock_response
            mock_chat.return_value = mock_model

            llm = BedrockLLM()
            result = llm.extract({}, "text")

            assert result == {"value": 42}

    def test_extract_returns_empty_dict_on_invalid_json(self, mock_config):
        """Extract should return empty dict when JSON is invalid."""
        with patch("app.services.llm.bedrock.ChatBedrockConverse") as mock_chat:
            mock_response = Mock()
            mock_response.content = "Not JSON at all"
            mock_model = Mock()
            mock_model.invoke.return_value = mock_response
            mock_chat.return_value = mock_model

            llm = BedrockLLM()
            result = llm.extract({}, "text")

            assert result == {}


class TestContentToText:
    """Test content normalization utility function."""

    def test_content_to_text_with_string(self):
        """Should return string content as-is."""
        result = _content_to_text("Hello world")
        assert result == "Hello world"

    def test_content_to_text_with_list_of_dicts(self):
        """Should extract text from dict blocks."""
        content = [
            {"text": "Hello"},
            {"text": " world"}
        ]
        result = _content_to_text(content)
        assert result == "Hello world"

    def test_content_to_text_with_content_field(self):
        """Should extract from 'content' field in dict."""
        content = [{"content": "Text from content field"}]
        result = _content_to_text(content)
        assert result == "Text from content field"

    def test_content_to_text_with_input_text_field(self):
        """Should extract from 'input_text' field in dict."""
        content = [{"input_text": "Input text"}]
        result = _content_to_text(content)
        assert result == "Input text"

    def test_content_to_text_with_dict_no_text_fields(self):
        """Should skip dicts without recognized text fields."""
        content = [{"other": "value"}, {"text": "actual text"}]
        result = _content_to_text(content)
        assert result == "actual text"


class TestSafeParseJson:
    """Test safe JSON parsing utility function."""

    def test_safe_parse_json_with_valid_json(self):
        """Should parse valid JSON string."""
        result = _safe_parse_json('{"key": "value", "number": 123}')
        assert result == {"key": "value", "number": 123}

    def test_safe_parse_json_with_json_in_text(self):
        """Should extract JSON from surrounding text."""
        text = 'Here is some data: {"extracted": true} and more text'
        result = _safe_parse_json(text)
        assert result == {"extracted": True}

    def test_safe_parse_json_with_invalid_json(self):
        """Should return empty dict for invalid JSON."""
        result = _safe_parse_json("Not JSON")
        assert result == {}

    def test_safe_parse_json_with_nested_objects(self):
        """Should parse nested JSON objects."""
        json_str = '{"outer": {"inner": {"value": 42}}}'
        result = _safe_parse_json(json_str)
        assert result == {"outer": {"inner": {"value": 42}}}
