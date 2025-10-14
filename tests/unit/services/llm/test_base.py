"""Unit tests for app.services.llm.base module.

Tests cover:
- Abstract LLM interface behavior
- Default implementations (set_callbacks, generate_stream)
- Abstract method enforcement
- Streaming chunking logic
"""

import pytest

from app.services.llm.base import LLM


class ConcreteLLM(LLM):
    """Concrete implementation of LLM for testing."""

    def __init__(self, response: str = "Test response"):
        self.response = response
        self.generate_calls = []
        self.extract_calls = []

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        context: dict | None = None,
    ) -> str:
        """Record calls and return test response."""
        self.generate_calls.append({
            "prompt": prompt,
            "system": system,
            "context": context,
        })
        return self.response

    def extract(
        self,
        schema: dict,
        text: str,
        instructions: str | None = None,
        context: dict | None = None,
    ) -> dict:
        """Record calls and return test extraction."""
        self.extract_calls.append({
            "schema": schema,
            "text": text,
            "instructions": instructions,
            "context": context,
        })
        return {"extracted": "data"}


class TestLLMAbstractMethods:
    """Test that LLM abstract methods must be implemented."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that LLM cannot be instantiated directly."""
        with pytest.raises(TypeError) as exc_info:
            LLM()

        error_message = str(exc_info.value)
        assert "abstract" in error_message.lower()

    def test_concrete_class_requires_generate(self):
        """Test that concrete class must implement generate."""
        class IncompleteGenerate(LLM):
            def extract(self, schema, text, instructions=None, context=None):
                return {}

        with pytest.raises(TypeError):
            IncompleteGenerate()

    def test_concrete_class_requires_extract(self):
        """Test that concrete class must implement extract."""
        class IncompleteExtract(LLM):
            def generate(self, prompt, system=None, context=None):
                return "response"

        with pytest.raises(TypeError):
            IncompleteExtract()

    def test_concrete_class_with_both_methods_instantiates(self):
        """Test that concrete class with both methods can be instantiated."""
        llm = ConcreteLLM()
        assert isinstance(llm, LLM)


class TestSetCallbacks:
    """Test set_callbacks default implementation."""

    def test_set_callbacks_accepts_none(self):
        """Test that set_callbacks accepts None without error."""
        llm = ConcreteLLM()
        result = llm.set_callbacks(None)
        assert result is None

    def test_set_callbacks_accepts_empty_list(self):
        """Test that set_callbacks accepts empty list."""
        llm = ConcreteLLM()
        result = llm.set_callbacks([])
        assert result is None

    def test_set_callbacks_accepts_callback_list(self):
        """Test that set_callbacks accepts list of callbacks."""
        llm = ConcreteLLM()
        callbacks = ["callback1", "callback2"]
        result = llm.set_callbacks(callbacks)
        assert result is None

    def test_set_callbacks_is_noop(self):
        """Test that set_callbacks does not store callbacks by default."""
        llm = ConcreteLLM()
        callbacks = ["callback1"]
        llm.set_callbacks(callbacks)

        # Verify it's a no-op (doesn't store anything)
        assert not hasattr(llm, "_callbacks")


class TestGenerate:
    """Test generate method implementation."""

    def test_generate_with_prompt_only(self):
        """Test generate with only prompt parameter."""
        llm = ConcreteLLM(response="Hello world")
        result = llm.generate("Test prompt")

        assert result == "Hello world"
        assert len(llm.generate_calls) == 1
        assert llm.generate_calls[0]["prompt"] == "Test prompt"
        assert llm.generate_calls[0]["system"] is None
        assert llm.generate_calls[0]["context"] is None

    def test_generate_with_system_prompt(self):
        """Test generate with system prompt."""
        llm = ConcreteLLM()
        result = llm.generate("User prompt", system="System instructions")

        assert result == "Test response"
        assert llm.generate_calls[0]["system"] == "System instructions"

    def test_generate_with_context(self):
        """Test generate with context dictionary."""
        llm = ConcreteLLM()
        context = {"user_id": "123", "session": "abc"}
        result = llm.generate("Prompt", context=context)

        assert result == "Test response"
        assert llm.generate_calls[0]["context"] == context

    def test_generate_with_all_parameters(self):
        """Test generate with all parameters."""
        llm = ConcreteLLM(response="Full response")
        context = {"key": "value"}

        result = llm.generate(
            prompt="Test prompt",
            system="System message",
            context=context,
        )

        assert result == "Full response"
        call = llm.generate_calls[0]
        assert call["prompt"] == "Test prompt"
        assert call["system"] == "System message"
        assert call["context"] == context


class TestGenerateStream:
    """Test generate_stream default implementation."""

    @pytest.mark.asyncio
    async def test_generate_stream_chunks_response(self):
        """Test that generate_stream chunks the full response."""
        llm = ConcreteLLM(response="Hello world")

        chunks = []
        async for chunk in llm.generate_stream("Test prompt"):
            chunks.append(chunk)

        # Verify chunks combine to full response
        full_text = "".join(chunks)
        assert full_text == "Hello world"

    @pytest.mark.asyncio
    async def test_generate_stream_default_chunk_size(self):
        """Test that default chunk size is 10 characters."""
        llm = ConcreteLLM(response="0123456789ABCDEFGHIJ")  # 20 chars

        chunks = []
        async for chunk in llm.generate_stream("Test"):
            chunks.append(chunk)

        # Should create 2 chunks of 10 chars each
        assert len(chunks) == 2
        assert chunks[0] == "0123456789"
        assert chunks[1] == "ABCDEFGHIJ"

    @pytest.mark.asyncio
    async def test_generate_stream_short_response(self):
        """Test streaming with response shorter than chunk size."""
        llm = ConcreteLLM(response="Short")

        chunks = []
        async for chunk in llm.generate_stream("Test"):
            chunks.append(chunk)

        # Single chunk with full response
        assert len(chunks) == 1
        assert chunks[0] == "Short"

    @pytest.mark.asyncio
    async def test_generate_stream_empty_response(self):
        """Test streaming with empty response."""
        llm = ConcreteLLM(response="")

        chunks = []
        async for chunk in llm.generate_stream("Test"):
            chunks.append(chunk)

        # Empty response produces no chunks (range(0, 0, 10) yields nothing)
        assert len(chunks) == 0

    @pytest.mark.asyncio
    async def test_generate_stream_calls_generate(self):
        """Test that generate_stream calls the generate method."""
        llm = ConcreteLLM(response="Test")

        chunks = []
        async for chunk in llm.generate_stream(
            prompt="User message",
            system="System",
            context={"key": "value"},
        ):
            chunks.append(chunk)

        # Verify generate was called with correct parameters
        assert len(llm.generate_calls) == 1
        call = llm.generate_calls[0]
        assert call["prompt"] == "User message"
        assert call["system"] == "System"
        assert call["context"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_generate_stream_preserves_content(self):
        """Test that streaming preserves exact content."""
        original = "Special chars: émojis 🎉 newlines\n\ttabs"
        llm = ConcreteLLM(response=original)

        chunks = []
        async for chunk in llm.generate_stream("Test"):
            chunks.append(chunk)

        reconstructed = "".join(chunks)
        assert reconstructed == original


class TestExtract:
    """Test extract method implementation."""

    def test_extract_with_schema_and_text(self):
        """Test extract with schema and text."""
        llm = ConcreteLLM()
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        text = "Extract this"

        result = llm.extract(schema, text)

        assert result == {"extracted": "data"}
        assert len(llm.extract_calls) == 1
        call = llm.extract_calls[0]
        assert call["schema"] == schema
        assert call["text"] == text
        assert call["instructions"] is None
        assert call["context"] is None

    def test_extract_with_instructions(self):
        """Test extract with instructions parameter."""
        llm = ConcreteLLM()
        schema = {"type": "object"}
        text = "Text"
        instructions = "Extract carefully"

        result = llm.extract(schema, text, instructions=instructions)

        assert result == {"extracted": "data"}
        assert llm.extract_calls[0]["instructions"] == "Extract carefully"

    def test_extract_with_context(self):
        """Test extract with context dictionary."""
        llm = ConcreteLLM()
        schema = {"type": "object"}
        text = "Text"
        context = {"user_id": "123"}

        result = llm.extract(schema, text, context=context)

        assert result == {"extracted": "data"}
        assert llm.extract_calls[0]["context"] == context

    def test_extract_with_all_parameters(self):
        """Test extract with all parameters."""
        llm = ConcreteLLM()
        schema = {"type": "object", "required": ["field"]}
        text = "Sample text"
        instructions = "Be precise"
        context = {"session": "abc"}

        result = llm.extract(
            schema=schema,
            text=text,
            instructions=instructions,
            context=context,
        )

        assert result == {"extracted": "data"}
        call = llm.extract_calls[0]
        assert call["schema"] == schema
        assert call["text"] == text
        assert call["instructions"] == instructions
        assert call["context"] == context


class TestLLMIntegration:
    """Integration tests for LLM interface."""

    def test_llm_can_be_used_polymorphically(self):
        """Test that LLM instances can be used through base interface."""
        def use_llm(llm: LLM) -> str:
            """Function that accepts LLM interface."""
            return llm.generate("Test prompt")

        concrete_llm = ConcreteLLM(response="Polymorphic response")
        result = use_llm(concrete_llm)

        assert result == "Polymorphic response"

    def test_multiple_implementations_coexist(self):
        """Test that multiple LLM implementations can coexist."""
        class AnotherLLM(LLM):
            def generate(self, prompt, system=None, context=None):
                return f"Another: {prompt}"

            def extract(self, schema, text, instructions=None, context=None):
                return {"another": "extraction"}

        llm1 = ConcreteLLM(response="First")
        llm2 = AnotherLLM()

        assert llm1.generate("test") == "First"
        assert llm2.generate("test") == "Another: test"

    @pytest.mark.asyncio
    async def test_streaming_with_custom_implementation(self):
        """Test that streaming works with custom implementations."""
        class CustomStreamLLM(LLM):
            def generate(self, prompt, system=None, context=None):
                return "Custom response"

            def extract(self, schema, text, instructions=None, context=None):
                return {}

        llm = CustomStreamLLM()
        chunks = []
        async for chunk in llm.generate_stream("Test"):
            chunks.append(chunk)

        # Uses default streaming implementation
        assert "".join(chunks) == "Custom response"
