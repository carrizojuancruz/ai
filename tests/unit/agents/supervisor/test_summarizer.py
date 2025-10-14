"""Tests for app/agents/supervisor/summarizer.py"""

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage
from langmem.short_term import RunningSummary

from app.agents.supervisor.summarizer import ConversationSummarizer


@pytest.mark.unit
class TestConversationSummarizerInit:
    """Test suite for ConversationSummarizer initialization."""

    def test_init_with_required_params(self):
        """Test initialization with required parameters."""
        mock_model = MagicMock()
        mock_counter = MagicMock(return_value=100)

        summarizer = ConversationSummarizer(
            model=mock_model,
            token_counter=mock_counter,
        )

        assert summarizer.model == mock_model
        assert summarizer.token_counter == mock_counter

    def test_init_with_custom_tail_budget(self):
        """Test initialization with custom tail_token_budget."""
        summarizer = ConversationSummarizer(
            model=MagicMock(),
            token_counter=MagicMock(),
            tail_token_budget=2000,
        )

        assert summarizer.tail_token_budget == 2000

    def test_init_with_custom_summary_max_tokens(self):
        """Test initialization with custom summary_max_tokens."""
        summarizer = ConversationSummarizer(
            model=MagicMock(),
            token_counter=MagicMock(),
            summary_max_tokens=512,
        )

        assert summarizer.summary_max_tokens == 512

    def test_init_with_custom_predicates(self):
        """Test initialization with custom include predicates."""
        def custom_include(msg):
            return True

        summarizer = ConversationSummarizer(
            model=MagicMock(),
            token_counter=MagicMock(),
            include_in_summary=custom_include,
            include_in_tail=custom_include,
        )

        assert summarizer.include_in_summary == custom_include
        assert summarizer.include_in_tail == custom_include

    def test_init_defaults_to_default_predicates(self):
        """Test that initialization defaults to _default_include_predicate."""
        summarizer = ConversationSummarizer(
            model=MagicMock(),
            token_counter=MagicMock(),
        )

        assert callable(summarizer.include_in_summary)
        assert callable(summarizer.include_in_tail)


@pytest.mark.unit
class TestConversationSummarizerSummarize:
    """Test suite for ConversationSummarizer.summarize method."""

    @pytest.fixture
    def mock_model(self):
        """Create mock LLM model."""
        mock = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "This is a concise summary of the conversation."
        mock.invoke.return_value = mock_response
        return mock

    @pytest.fixture
    def mock_token_counter(self):
        """Create mock token counter."""
        return MagicMock(return_value=50)

    @pytest.fixture
    def summarizer(self, mock_model, mock_token_counter):
        """Create ConversationSummarizer instance."""
        return ConversationSummarizer(
            model=mock_model,
            token_counter=mock_token_counter,
            tail_token_budget=500,
            summary_max_tokens=256,
        )

    def test_summarize_empty_messages_returns_empty_dict(self, summarizer):
        """Test that summarizing empty messages returns empty dict."""
        result = summarizer.summarize([], {})
        assert result == {}

    def test_summarize_basic_conversation(self, summarizer, sample_messages):
        """Test basic conversation summarization."""
        result = summarizer.summarize(sample_messages, {})

        assert result == {}

    def test_summarize_preserves_tail_messages(self, summarizer, sample_long_messages, mock_token_counter):
        """Test that summarize preserves recent messages within tail budget."""
        mock_token_counter.side_effect = lambda msgs: len(msgs) * 50

        result = summarizer.summarize(sample_long_messages, {})

        messages = result.get("messages", [])
        assert len(messages) > 0

    def test_summarize_creates_system_message_summary(self, summarizer, sample_long_messages):
        """Test that summarize creates a SystemMessage with summary."""
        result = summarizer.summarize(sample_long_messages, {})

        messages = result.get("messages", [])
        summary_msg = None
        for msg in messages:
            if isinstance(msg, SystemMessage):
                summary_msg = msg
                break

        assert summary_msg is not None
        assert "Summary" in summary_msg.content or "summary" in summary_msg.content.lower()

    def test_summarize_calls_model_invoke(self, summarizer, sample_long_messages, mock_model):
        """Test that summarize calls model.invoke."""
        summarizer.summarize(sample_long_messages, {})

        mock_model.invoke.assert_called_once()

    def test_summarize_creates_running_summary_in_context(self, summarizer, sample_long_messages):
        """Test that summarize creates RunningSummary in context."""
        result = summarizer.summarize(sample_long_messages, {})

        context = result.get("context", {})
        assert "running_summary" in context
        assert isinstance(context["running_summary"], RunningSummary)

    def test_summarize_running_summary_has_correct_structure(self, summarizer, sample_long_messages):
        """Test that RunningSummary has correct structure."""
        result = summarizer.summarize(sample_long_messages, {})

        running_summary = result["context"]["running_summary"]
        assert hasattr(running_summary, "summary")
        assert hasattr(running_summary, "summarized_message_ids")
        assert hasattr(running_summary, "last_summarized_message_id")

    def test_summarize_handles_model_error_gracefully(self, summarizer, sample_messages, mock_model):
        """Test that summarize handles model errors gracefully."""
        mock_model.invoke.side_effect = Exception("Model error")

        result = summarizer.summarize(sample_messages, {})

        assert result == {}

    def test_summarize_filters_handoff_messages(self, summarizer, mock_token_counter):
        """Test that summarize filters out handoff messages."""
        mock_token_counter.return_value = 600

        messages = [
            HumanMessage(content="User question", id="msg_1"),
            AIMessage(
                content="Returning control to supervisor",
                id="msg_2",
                response_metadata={"is_handoff_back": True},
            ),
            AIMessage(content="Regular response", id="msg_3"),
        ]

        summarizer.summarize(messages, {})

        assert summarizer.model.invoke.called

    def test_summarize_filters_context_messages(self, summarizer):
        """Test that summarize filters out context profile messages."""
        messages = [
            HumanMessage(content="CONTEXT_PROFILE: user info", id="msg_1"),
            HumanMessage(content="Regular user message", id="msg_2"),
            AIMessage(content="Response", id="msg_3"),
        ]

        summarizer.summarize(messages, {})


    def test_summarize_respects_tail_token_budget(self, summarizer, mock_token_counter):
        """Test that summarize respects tail_token_budget."""
        messages = [HumanMessage(content=f"Message {i}", id=f"msg_{i}") for i in range(20)]

        mock_token_counter.return_value = 100

        result = summarizer.summarize(messages, {})

        tail_messages = [m for m in result.get("messages", []) if not isinstance(m, (SystemMessage, RemoveMessage))]
        assert len(tail_messages) <= 6

    def test_summarize_returns_remove_all_messages(self, summarizer, sample_messages):
        """Test that summarize includes RemoveMessage for old messages."""
        result = summarizer.summarize(sample_messages, {})

        assert result == {}


@pytest.mark.unit
class TestConversationSummarizerAsNode:
    """Test suite for ConversationSummarizer.as_node method."""

    @pytest.fixture
    def summarizer(self):
        """Create summarizer instance."""
        mock_model = MagicMock()
        mock_model.invoke.return_value = MagicMock(content="Summary text")

        return ConversationSummarizer(
            model=mock_model,
            token_counter=MagicMock(return_value=50),
        )

    def test_as_node_returns_callable(self, summarizer):
        """Test that as_node returns a callable function."""
        node = summarizer.as_node()
        assert callable(node)

    def test_node_callable_accepts_state(self, summarizer, sample_messages):
        """Test that node callable accepts state dict."""
        node = summarizer.as_node()

        state = {"messages": sample_messages, "context": {}}
        result = node(state)

        assert isinstance(result, dict)

    def test_node_callable_returns_dict(self, summarizer, sample_messages):
        """Test that node callable returns dict."""
        node = summarizer.as_node()

        state = {"messages": sample_messages, "context": {}}
        result = node(state)

        assert isinstance(result, dict)

    def test_node_handles_empty_state(self, summarizer):
        """Test that node handles empty state."""
        node = summarizer.as_node()

        state = {}
        result = node(state)

        assert isinstance(result, dict)


@pytest.mark.unit
class TestConversationSummarizerHelperMethods:
    """Test suite for ConversationSummarizer helper methods."""

    @pytest.fixture
    def summarizer(self):
        """Create summarizer instance."""
        return ConversationSummarizer(
            model=MagicMock(),
            token_counter=MagicMock(),
        )

    def test_messages_to_transcript(self, summarizer):
        """Test _messages_to_transcript method."""
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!"),
        ]

        transcript = summarizer._messages_to_transcript(messages)

        assert isinstance(transcript, str)
        assert "User:" in transcript or "Hello" in transcript
        assert "Assistant:" in transcript or "Hi there" in transcript

    def test_format_role_human(self, summarizer):
        """Test _format_role for human messages."""
        msg = HumanMessage(content="Test")
        role = summarizer._format_role(msg)
        assert role == "User"

    def test_format_role_ai(self, summarizer):
        """Test _format_role for AI messages."""
        msg = AIMessage(content="Test")
        role = summarizer._format_role(msg)
        assert role == "Assistant"

    def test_format_role_system(self, summarizer):
        """Test _format_role for system messages."""
        msg = SystemMessage(content="Test")
        role = summarizer._format_role(msg)
        assert role == "System"

    def test_to_plain_text_string(self, summarizer):
        """Test _to_plain_text with string input."""
        result = summarizer._to_plain_text("Hello world")
        assert result == "Hello world"

    def test_to_plain_text_none(self, summarizer):
        """Test _to_plain_text with None."""
        result = summarizer._to_plain_text(None)
        assert result == ""

    def test_to_plain_text_list_of_dicts(self, summarizer):
        """Test _to_plain_text with list of content blocks."""
        content = [
            {"type": "text", "text": "First part"},
            {"type": "text", "text": "Second part"},
        ]
        result = summarizer._to_plain_text(content)
        assert "First part" in result
        assert "Second part" in result

    def test_to_plain_text_object_with_content(self, summarizer):
        """Test _to_plain_text with object having .content attribute."""
        mock_obj = MagicMock()
        mock_obj.content = "Content from object"
        result = summarizer._to_plain_text(mock_obj)
        assert result == "Content from object"

    def test_default_include_predicate_includes_user_messages(self, summarizer):
        """Test _default_include_predicate includes user messages."""
        msg = HumanMessage(content="User message")
        result = summarizer._default_include_predicate(msg)
        assert result is True

    def test_default_include_predicate_includes_ai_messages(self, summarizer):
        """Test _default_include_predicate includes AI messages."""
        msg = AIMessage(content="AI message")
        result = summarizer._default_include_predicate(msg)
        assert result is True

    def test_default_include_predicate_excludes_system_messages(self, summarizer):
        """Test _default_include_predicate excludes system messages."""
        msg = SystemMessage(content="System message")
        result = summarizer._default_include_predicate(msg)
        assert result is False

    def test_default_include_predicate_excludes_handoff_messages(self, summarizer):
        """Test _default_include_predicate excludes handoff messages."""
        msg = AIMessage(
            content="Returning control",
            response_metadata={"is_handoff_back": True},
        )
        result = summarizer._default_include_predicate(msg)
        assert result is False

    def test_default_include_predicate_excludes_context_profile_messages(self, summarizer):
        """Test _default_include_predicate excludes CONTEXT_PROFILE messages."""
        msg = HumanMessage(content="CONTEXT_PROFILE: user data")
        result = summarizer._default_include_predicate(msg)
        assert result is False

    def test_default_include_predicate_excludes_context_tailoring_messages(self, summarizer):
        """Test _default_include_predicate excludes context tailoring messages."""
        msg = HumanMessage(content="Relevant context for tailoring this turn: data")
        result = summarizer._default_include_predicate(msg)
        assert result is False


@pytest.mark.unit
class TestConversationSummarizerEdgeCases:
    """Test suite for edge cases in ConversationSummarizer."""

    def test_summarize_with_only_system_messages(self):
        """Test summarize with only system messages (should be filtered)."""
        mock_model = MagicMock()
        mock_model.invoke.return_value = MagicMock(content="Summary")

        summarizer = ConversationSummarizer(
            model=mock_model,
            token_counter=MagicMock(return_value=50),
        )

        messages = [
            SystemMessage(content="System 1"),
            SystemMessage(content="System 2"),
        ]

        result = summarizer.summarize(messages, {})

        assert isinstance(result, dict)

    def test_summarize_with_empty_summary_response(self):
        """Test handling of empty summary from model."""
        mock_model = MagicMock()
        mock_model.invoke.return_value = MagicMock(content="")

        summarizer = ConversationSummarizer(
            model=mock_model,
            token_counter=MagicMock(return_value=50),
        )

        messages = [
            HumanMessage(content="Test"),
            AIMessage(content="Response"),
        ]

        result = summarizer.summarize(messages, {})

        assert result == {}

    def test_summarize_with_very_long_messages(self):
        """Test summarize with messages exceeding tail budget multiple times."""
        mock_model = MagicMock()
        mock_model.invoke.return_value = MagicMock(content="Summary of conversation")

        def token_counter(msgs):
            return len(msgs) * 1000

        summarizer = ConversationSummarizer(
            model=mock_model,
            token_counter=token_counter,
            tail_token_budget=500,
        )

        messages = [
            HumanMessage(content="msg " * 500, id=f"msg_{i}")
            for i in range(10)
        ]

        result = summarizer.summarize(messages, {})

        assert "messages" in result
        messages_result = result.get("messages", [])
        assert len(messages_result) < len(messages)
