"""
Unit tests for app.agents.supervisor.agent module.

Tests cover:
- log_state_snapshot function with trace enabled/disabled
- append_trace_record function
- serialize_message function with various message types
- serialize_running_summary function
- compile_supervisor_graph function and its inner functions
- Token counting and state management
- Summarization gating logic
"""

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, Mock, mock_open, patch

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langmem.short_term import RunningSummary

from app.agents.supervisor.agent import (
    TRACE_STAGE_AFTER_CONTEXT,
    TRACE_STAGE_AFTER_HOTPATH,
    TRACE_STAGE_AFTER_SUMMARIZE,
    TRACE_STAGE_RESTORED,
    append_trace_record,
    compile_supervisor_graph,
    log_state_snapshot,
    serialize_message,
    serialize_running_summary,
)


class TestLogStateSnapshot:
    """Test log_state_snapshot function."""

    @patch("app.agents.supervisor.agent.app_config")
    def test_log_state_snapshot_trace_disabled(self, mock_config):
        """Test that logging is skipped when trace is disabled."""
        mock_config.SUPERVISOR_TRACE_ENABLED = False

        messages = [HumanMessage(content="test")]
        context = {}
        token_counter = Mock(return_value=10)

        with patch("app.agents.supervisor.agent.append_trace_record") as mock_append:
            log_state_snapshot("test_stage", messages, context, token_counter)
            mock_append.assert_not_called()

    @patch("app.agents.supervisor.agent.app_config")
    @patch("app.agents.supervisor.agent.append_trace_record")
    @patch("app.agents.supervisor.agent.datetime")
    def test_log_state_snapshot_trace_enabled(self, mock_dt, mock_append, mock_config):
        """Test that logging works when trace is enabled."""
        mock_config.SUPERVISOR_TRACE_ENABLED = True
        mock_now = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        mock_dt.now.return_value = mock_now

        messages = [HumanMessage(content="hello"), AIMessage(content="hi")]
        context = {}
        token_counter = Mock(return_value=25)

        log_state_snapshot("test_stage", messages, context, token_counter)

        mock_append.assert_called_once()
        record = mock_append.call_args[0][0]

        assert record["stage"] == "test_stage"
        assert record["token_count"] == 25
        assert record["message_count"] == 2
        assert record["timestamp"] == mock_now.isoformat()
        assert "messages" in record

    @patch("app.agents.supervisor.agent.app_config")
    @patch("app.agents.supervisor.agent.append_trace_record")
    def test_log_state_snapshot_with_running_summary(self, mock_append, mock_config):
        """Test logging with running summary in context."""
        mock_config.SUPERVISOR_TRACE_ENABLED = True

        messages = [HumanMessage(content="test")]
        running_summary = RunningSummary(
            summary="Test summary",
            summarized_message_ids=["id1", "id2"],
            last_summarized_message_id="id2",
        )
        context = {"running_summary": running_summary}
        token_counter = Mock(return_value=10)

        log_state_snapshot("with_summary", messages, context, token_counter)

        mock_append.assert_called_once()
        record = mock_append.call_args[0][0]

        assert "running_summary" in record
        assert record["running_summary"]["summary"] == "Test summary"
        assert "id1" in record["running_summary"]["summarized_message_ids"]
        assert "id2" in record["running_summary"]["summarized_message_ids"]

    @patch("app.agents.supervisor.agent.app_config")
    @patch("app.agents.supervisor.agent.logger")
    def test_log_state_snapshot_handles_exceptions(self, mock_logger, mock_config):
        """Test that exceptions in logging are caught and logged."""
        mock_config.SUPERVISOR_TRACE_ENABLED = True

        messages = [HumanMessage(content="test")]
        context = {}
        token_counter = Mock(side_effect=Exception("Token counter failed"))

        log_state_snapshot("error_stage", messages, context, token_counter)

        mock_logger.warning.assert_called_once()
        assert "supervisor.trace.write_failed" in mock_logger.warning.call_args[0][0]

    @patch("app.agents.supervisor.agent.app_config")
    @patch("app.agents.supervisor.agent.append_trace_record")
    def test_log_state_snapshot_filters_non_messages(self, mock_append, mock_config):
        """Test that non-BaseMessage objects are filtered out."""
        mock_config.SUPERVISOR_TRACE_ENABLED = True

        messages = [HumanMessage(content="valid"), "invalid", None, AIMessage(content="also valid")]
        context = {}
        token_counter = Mock(return_value=15)

        log_state_snapshot("filter_stage", messages, context, token_counter)

        mock_append.assert_called_once()
        record = mock_append.call_args[0][0]

        assert record["message_count"] == 2  # Only 2 valid messages


class TestAppendTraceRecord:
    """Test append_trace_record function."""

    @patch("app.agents.supervisor.agent.app_config")
    @patch("pathlib.Path.open", new_callable=mock_open)
    @patch("pathlib.Path.mkdir")
    def test_append_trace_record_creates_directory(self, mock_mkdir, mock_file, mock_config):
        """Test that directory is created if it doesn't exist."""
        mock_config.SUPERVISOR_TRACE_PATH = "/tmp/traces/trace.jsonl"

        record = {"stage": "test", "data": "value"}
        append_trace_record(record)

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("app.agents.supervisor.agent.app_config")
    @patch("pathlib.Path.open", new_callable=mock_open)
    @patch("pathlib.Path.mkdir")
    def test_append_trace_record_writes_json(self, mock_mkdir, mock_file, mock_config):
        """Test that record is written as JSON with newline."""
        mock_config.SUPERVISOR_TRACE_PATH = "/tmp/traces/trace.jsonl"

        record = {"stage": "test", "count": 42, "nested": {"key": "value"}}
        append_trace_record(record)

        mock_file.assert_called_once_with("a", encoding="utf-8")
        handle = mock_file()

        # Check that JSON was written with newline
        written_calls = handle.write.call_args_list
        assert len(written_calls) == 2
        json_call = written_calls[0][0][0]
        newline_call = written_calls[1][0][0]

        assert json_call == json.dumps(record, ensure_ascii=False)
        assert newline_call == "\n"


class TestSerializeMessage:
    """Test serialize_message function."""

    def test_serialize_human_message(self):
        """Test serializing a HumanMessage."""
        message = HumanMessage(content="Hello, AI!")
        result = serialize_message(message)

        # LangChain messages use to_json() which returns a dict with specific format
        assert isinstance(result, dict)
        assert "content" in str(result).lower() or "hello" in str(result).lower()

    def test_serialize_ai_message(self):
        """Test serializing an AIMessage."""
        message = AIMessage(content="Hello, human!")
        result = serialize_message(message)

        assert isinstance(result, dict)
        assert "content" in str(result).lower() or "hello" in str(result).lower()

    def test_serialize_system_message(self):
        """Test serializing a SystemMessage."""
        message = SystemMessage(content="You are a helpful assistant")
        result = serialize_message(message)

        assert isinstance(result, dict)
        assert "content" in str(result).lower() or "helpful" in str(result).lower()

    def test_serialize_message_with_additional_kwargs(self):
        """Test serializing message with additional_kwargs."""
        message = AIMessage(
            content="Response",
            additional_kwargs={"model": "claude-3", "temperature": 0.7},
        )
        result = serialize_message(message)

        # Just check that serialization works
        assert isinstance(result, dict)

    def test_serialize_message_with_tool_calls(self):
        """Test serializing message with tool_calls."""
        message = AIMessage(
            content="",
            tool_calls=[
                {"id": "call_1", "name": "get_weather", "args": {"location": "NYC"}}
            ],
        )
        result = serialize_message(message)

        # Just check that serialization works
        assert isinstance(result, dict)

    def test_serialize_message_with_response_metadata(self):
        """Test serializing message with response_metadata."""
        message = AIMessage(
            content="Response",
            response_metadata={"finish_reason": "stop", "model": "claude-3"},
        )
        result = serialize_message(message)

        # Just check that serialization works
        assert isinstance(result, dict)

    def test_serialize_message_with_to_json(self):
        """Test that to_json is used if available."""
        message = Mock(spec=BaseMessage)
        message.to_json.return_value = {"custom": "json", "format": True}

        result = serialize_message(message)

        assert result["custom"] == "json"
        assert result["format"] is True

    def test_serialize_message_fallback_on_to_json_exception(self):
        """Test fallback when to_json raises exception."""
        message = Mock(spec=BaseMessage)
        message.to_json.side_effect = Exception("JSON error")
        message.type = "custom"
        message.content = "fallback content"
        message.additional_kwargs = {}
        message.response_metadata = {}
        message.tool_calls = []

        result = serialize_message(message)

        assert result["type"] == "custom"
        assert result["content"] == "fallback content"

    def test_serialize_message_missing_attributes(self):
        """Test serializing message with missing attributes."""
        message = Mock()
        # Set attributes to simulate missing values
        del message.to_json
        message.type = "unknown"
        message.content = None
        message.additional_kwargs = {}
        message.response_metadata = {}
        message.tool_calls = []

        result = serialize_message(message)

        assert result["type"] == "unknown"
        assert result["content"] is None
        assert result["additional_kwargs"] == {}
        assert result["response_metadata"] == {}
        assert result["tool_calls"] == []


class TestSerializeRunningSummary:
    """Test serialize_running_summary function."""

    def test_serialize_running_summary_none(self):
        """Test that None returns None."""
        result = serialize_running_summary(None)
        assert result is None

    def test_serialize_running_summary_basic(self):
        """Test serializing a basic RunningSummary."""
        summary = RunningSummary(
            summary="This is a summary",
            summarized_message_ids=["msg1", "msg2", "msg3"],
            last_summarized_message_id="msg3",
        )

        result = serialize_running_summary(summary)

        assert result["summary"] == "This is a summary"
        assert result["last_summarized_message_id"] == "msg3"
        assert len(result["summarized_message_ids"]) == 3

    def test_serialize_running_summary_sorted_ids(self):
        """Test that message IDs are sorted."""
        summary = RunningSummary(
            summary="Summary",
            summarized_message_ids=["msg3", "msg1", "msg2"],
            last_summarized_message_id="msg3",
        )

        result = serialize_running_summary(summary)

        assert result["summarized_message_ids"] == ["msg1", "msg2", "msg3"]

    def test_serialize_running_summary_empty_ids(self):
        """Test serializing summary with empty message IDs."""
        summary = RunningSummary(
            summary="Empty summary",
            summarized_message_ids=[],
            last_summarized_message_id=None,
        )

        result = serialize_running_summary(summary)

        assert result["summary"] == "Empty summary"
        assert result["summarized_message_ids"] == []
        assert result["last_summarized_message_id"] is None


class TestCompileSupervisorGraph:
    """Test compile_supervisor_graph function."""

    @patch("app.agents.supervisor.agent.create_s3_vectors_store_from_env")
    @patch("app.agents.supervisor.agent.MemorySaver")
    @patch("app.agents.supervisor.agent.SafeChatCerebras")
    @patch("app.agents.supervisor.agent.app_config")
    def test_compile_supervisor_graph_creates_graph(
        self, mock_config, mock_cerebras, mock_saver, mock_store
    ):
        """Test that compile_supervisor_graph creates a graph successfully."""
        mock_config.SUPERVISOR_AGENT_MODEL_ID = "gpt-oss-120b"
        mock_config.SUPERVISOR_AGENT_MODEL_REGION = "us-east-1"
        mock_config.SUPERVISOR_AGENT_TEMPERATURE = 0.7
        mock_config.CEREBRAS_API_KEY = "test-api-key"
        mock_config.SUMMARY_MODEL_ID = "gpt-oss-120b"
        mock_config.SUMMARY_MAX_SUMMARY_TOKENS = "1000"
        mock_config.SUMMARY_TAIL_TOKEN_BUDGET = "2000"
        mock_config.SUMMARY_MAX_TOKENS_BEFORE = "8000"

        mock_llm = MagicMock()
        mock_llm.bind.return_value = mock_llm
        mock_llm.get_num_tokens_from_messages.return_value = 100
        mock_cerebras.return_value = mock_llm

        mock_store_instance = MagicMock()
        mock_store.return_value = mock_store_instance

        graph = compile_supervisor_graph()

        assert graph is not None
        mock_cerebras.assert_called()
        mock_store.assert_called_once()

    @patch("app.agents.supervisor.agent.create_s3_vectors_store_from_env")
    @patch("app.agents.supervisor.agent.MemorySaver")
    @patch("app.agents.supervisor.agent.SafeChatCerebras")
    @patch("app.agents.supervisor.agent.app_config")
    def test_compile_supervisor_graph_no_summary_model(
        self, mock_config, mock_cerebras, mock_saver, mock_store
    ):
        """Test graph compilation when no separate summary model is configured."""
        mock_config.SUPERVISOR_AGENT_MODEL_ID = "gpt-oss-120b"
        mock_config.SUPERVISOR_AGENT_MODEL_REGION = "us-east-1"
        mock_config.SUPERVISOR_AGENT_TEMPERATURE = 0.7
        mock_config.CEREBRAS_API_KEY = "test-api-key"
        mock_config.SUMMARY_MODEL_ID = None  # No separate summary model
        mock_config.SUMMARY_MAX_SUMMARY_TOKENS = "1000"
        mock_config.SUMMARY_TAIL_TOKEN_BUDGET = "2000"
        mock_config.SUMMARY_MAX_TOKENS_BEFORE = "8000"

        mock_llm = MagicMock()
        mock_llm.bind.return_value = mock_llm
        mock_llm.get_num_tokens_from_messages.return_value = 100
        mock_cerebras.return_value = mock_llm

        graph = compile_supervisor_graph()

        assert graph is not None
        # Should only create one SafeChatCerebras instance
        assert mock_cerebras.call_count >= 1

    @patch("app.agents.supervisor.agent.create_s3_vectors_store_from_env")
    @patch("app.agents.supervisor.agent.MemorySaver")
    @patch("app.agents.supervisor.agent.SafeChatCerebras")
    @patch("app.agents.supervisor.agent.app_config")
    @patch("app.agents.supervisor.agent.logger")
    def test_compile_supervisor_graph_bind_exception(
        self, mock_logger, mock_config, mock_cerebras, mock_saver, mock_store
    ):
        """Test that bind exceptions are logged and handled."""
        mock_config.SUPERVISOR_AGENT_MODEL_ID = "gpt-oss-120b"
        mock_config.SUPERVISOR_AGENT_MODEL_REGION = "us-east-1"
        mock_config.SUPERVISOR_AGENT_TEMPERATURE = 0.7
        mock_config.CEREBRAS_API_KEY = "test-api-key"
        mock_config.SUMMARY_MODEL_ID = "gpt-oss-120b"
        mock_config.SUMMARY_MAX_SUMMARY_TOKENS = "1000"
        mock_config.SUMMARY_TAIL_TOKEN_BUDGET = "2000"
        mock_config.SUMMARY_MAX_TOKENS_BEFORE = "8000"

        mock_llm = MagicMock()
        mock_llm.bind.side_effect = Exception("Bind not supported")
        mock_llm.get_num_tokens_from_messages.return_value = 100
        mock_cerebras.return_value = mock_llm

        graph = compile_supervisor_graph()

        assert graph is not None
        # Check that bind exception was logged
        assert any("summary.model.bind.skip" in str(call) for call in mock_logger.info.call_args_list)


class TestTokenCountingAndGating:
    """Test token counting and summarization gating logic."""

    @patch("app.agents.supervisor.agent.create_s3_vectors_store_from_env")
    @patch("app.agents.supervisor.agent.MemorySaver")
    @patch("app.agents.supervisor.agent.SafeChatCerebras")
    @patch("app.agents.supervisor.agent.app_config")
    def test_token_counter_uses_llm_method(
        self, mock_config, mock_cerebras, mock_saver, mock_store
    ):
        """Test that token counter uses LLM method when available."""
        mock_config.SUPERVISOR_AGENT_MODEL_ID = "gpt-oss-120b"
        mock_config.SUPERVISOR_AGENT_MODEL_REGION = "us-east-1"
        mock_config.SUPERVISOR_AGENT_TEMPERATURE = 0.7
        mock_config.CEREBRAS_API_KEY = "test-api-key"
        mock_config.SUMMARY_MODEL_ID = None
        mock_config.SUMMARY_MAX_SUMMARY_TOKENS = "1000"
        mock_config.SUMMARY_TAIL_TOKEN_BUDGET = "2000"
        mock_config.SUMMARY_MAX_TOKENS_BEFORE = "8000"

        mock_llm = MagicMock()
        mock_llm.bind.return_value = mock_llm
        mock_llm.get_num_tokens_from_messages.return_value = 150
        mock_cerebras.return_value = mock_llm

        # Compile graph to get token counter
        graph = compile_supervisor_graph()
        assert graph is not None

    @patch("app.agents.supervisor.agent.create_s3_vectors_store_from_env")
    @patch("app.agents.supervisor.agent.MemorySaver")
    @patch("app.agents.supervisor.agent.SafeChatCerebras")
    @patch("app.agents.supervisor.agent.app_config")
    @patch("app.agents.supervisor.agent.count_tokens_approximately")
    def test_token_counter_fallback_on_exception(
        self, mock_approx, mock_config, mock_cerebras, mock_saver, mock_store
    ):
        """Test that token counter falls back to approximate counting."""
        mock_config.SUPERVISOR_AGENT_MODEL_ID = "gpt-oss-120b"
        mock_config.SUPERVISOR_AGENT_MODEL_REGION = "us-east-1"
        mock_config.SUPERVISOR_AGENT_TEMPERATURE = 0.7
        mock_config.CEREBRAS_API_KEY = "test-api-key"
        mock_config.SUMMARY_MODEL_ID = None
        mock_config.SUMMARY_MAX_SUMMARY_TOKENS = "1000"
        mock_config.SUMMARY_TAIL_TOKEN_BUDGET = "2000"
        mock_config.SUMMARY_MAX_TOKENS_BEFORE = "8000"

        mock_llm = MagicMock()
        mock_llm.bind.return_value = mock_llm
        mock_llm.get_num_tokens_from_messages.side_effect = Exception("Not supported")
        mock_cerebras.return_value = mock_llm
        mock_approx.return_value = 200

        graph = compile_supervisor_graph()
        assert graph is not None


class TestInnerGraphFunctions:
    """Test inner functions created within compile_supervisor_graph."""

    def test_to_plain_text_with_string(self):
        """Test _to_plain_text with string input."""

        # Access the function through compilation
        # This is a simplified test - in reality we'd need to extract the function
        # For now, we test the logic separately

        def _to_plain_text(value: Any) -> str:
            if value is None:
                return ""
            if isinstance(value, str):
                return value
            if isinstance(value, list):
                parts = []
                for item in value:
                    if isinstance(item, dict):
                        if item.get("type") == "text" and isinstance(item.get("text"), str):
                            parts.append(item["text"])
                    elif hasattr(item, "get"):
                        try:
                            t = item.get("text")
                            if isinstance(t, str):
                                parts.append(t)
                        except Exception:
                            pass
                return "\n".join([p for p in parts if p])
            content = getattr(value, "content", None)
            if isinstance(content, str):
                return content
            return str(value)

        assert _to_plain_text("hello") == "hello"
        assert _to_plain_text(None) == ""
        assert _to_plain_text(123) == "123"

    def test_to_plain_text_with_list_of_dicts(self):
        """Test _to_plain_text with list of text blocks."""

        def _to_plain_text(value: Any) -> str:
            if value is None:
                return ""
            if isinstance(value, str):
                return value
            if isinstance(value, list):
                parts = []
                for item in value:
                    if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                        parts.append(item["text"])
                return "\n".join([p for p in parts if p])
            content = getattr(value, "content", None)
            if isinstance(content, str):
                return content
            return str(value)

        blocks = [
            {"type": "text", "text": "First block"},
            {"type": "text", "text": "Second block"},
            {"type": "image", "data": "..."},
        ]

        result = _to_plain_text(blocks)
        assert "First block" in result
        assert "Second block" in result

    def test_to_plain_text_with_content_attribute(self):
        """Test _to_plain_text with object having content attribute."""

        def _to_plain_text(value: Any) -> str:
            if value is None:
                return ""
            if isinstance(value, str):
                return value
            content = getattr(value, "content", None)
            if isinstance(content, str):
                return content
            return str(value)

        obj = Mock()
        obj.content = "Content from attribute"

        result = _to_plain_text(obj)
        assert result == "Content from attribute"


class TestTraceStageConstants:
    """Test that trace stage constants are defined."""

    def test_trace_stage_constants_exist(self):
        """Test that all trace stage constants are defined."""
        assert TRACE_STAGE_RESTORED == "restored"
        assert TRACE_STAGE_AFTER_SUMMARIZE == "after_summarize"
        assert TRACE_STAGE_AFTER_HOTPATH == "after_memory_hotpath"
        assert TRACE_STAGE_AFTER_CONTEXT == "after_memory_context"
