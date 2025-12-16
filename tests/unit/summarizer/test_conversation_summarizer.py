"""Tests for the ConversationSummarizer."""

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.supervisor.summarizer import ConversationSummarizer


class TestConversationSummarizer:
    """Test the ConversationSummarizer functionality."""

    @pytest.fixture
    def mock_model(self):
        """Mock model that returns a summary."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "- User asked about spending\n- Assistant provided analysis"
        mock_model.invoke.return_value = mock_response
        return mock_model

    def test_summarizer_filters_injected_context(self, mock_model):
        """Test that injected context messages are excluded from summarization."""
        messages = [
            # Injected context - should be excluded
            AIMessage(
                content="CONTEXT_PROFILE: name=Rick; city=Los Angeles; language=en-US; blocked_topics=dog diseases, religion.",
                id="context_1"
            ),
            # Memory injection - should be excluded
            AIMessage(
                content="Relevant context for tailoring this turn:\nCURRENT TIME: Now: 2025-09-24 21:25 UTC\nEPISODIC MEMORIES: ...",
                id="memory_1"
            ),
            # Conversational messages - should be included
            HumanMessage(content="How much have I spent on coffee last year?", id="human_1"),
            AIMessage(content="Let me check your transaction data for coffee spending...", id="ai_1"),
            HumanMessage(content="Ok, and for groceries?", id="human_2"),
            AIMessage(content="Let me check grocery spending...", id="ai_2"),
        ]

        summarizer = ConversationSummarizer(
            model=mock_model,
            tail_token_budget=0,  # Force preservation of last turn only
            summary_max_tokens=100,
        )

        context = {}
        result = summarizer.summarize(messages, context)

        # Should have called the model (summarization occurred)
        mock_model.invoke.assert_called_once()

        # Check that summary was created
        assert "messages" in result
        assert "context" in result
        assert "running_summary" in result["context"]

        # Check that running summary contains the summarized message IDs
        running_summary = result["context"]["running_summary"]
        # Should only have summarized the head conversational messages (human_1, ai_1)
        assert len(running_summary.summarized_message_ids) == 2
        assert "human_1" in running_summary.summarized_message_ids
        assert "ai_1" in running_summary.summarized_message_ids

    def test_summarizer_filters_handoff_markers(self, mock_model):
        """Test that handoff back messages are excluded from summarization."""
        messages = [
            HumanMessage(content="How much have I spent?", id="human_1"),
            AIMessage(content="Let me analyze that for you.", id="ai_1"),
            # Handoff back - should be excluded
            AIMessage(
                content="Analysis completed. Returning control to supervisor.",
                response_metadata={"is_handoff_back": True},
                id="handoff_1"
            ),
            HumanMessage(content="Thanks! Any tips?", id="human_2"),
            AIMessage(content="A few tips...", id="ai_2"),
        ]

        summarizer = ConversationSummarizer(
            model=mock_model,
            tail_token_budget=0,
            summary_max_tokens=100,
        )

        context = {}
        result = summarizer.summarize(messages, context)

        # Should have called the model (summarization occurred)
        mock_model.invoke.assert_called_once()

        # Check that running summary contains the summarized message IDs
        running_summary = result["context"]["running_summary"]
        assert len(running_summary.summarized_message_ids) == 2
        assert "human_1" in running_summary.summarized_message_ids
        assert "ai_1" in running_summary.summarized_message_ids
        assert "handoff_1" not in running_summary.summarized_message_ids

    def test_summarizer_preserves_conversational_tail(self, mock_model):
        """Test that conversational messages are preserved in the tail."""
        messages = [
            HumanMessage(content="First question?", id="human_1"),
            AIMessage(content="First answer.", id="ai_1"),
            HumanMessage(content="Second question?", id="human_2"),
            AIMessage(content="Second answer.", id="ai_2"),
            HumanMessage(content="Third question?", id="human_3"),  # Should be in tail
        ]

        summarizer = ConversationSummarizer(
            model=mock_model,
            tail_token_budget=0,
            summary_max_tokens=100,
        )

        context = {}
        result = summarizer.summarize(messages, context)

        # Should have called the model (summarization occurred)
        mock_model.invoke.assert_called_once()

        # Should have output messages
        assert "messages" in result
        output_messages = result["messages"]

        # Should have RemoveMessage + System summary + tail messages
        assert len(output_messages) >= 2  # At least remove + summary

        out_ids = {getattr(m, "id", None) for m in output_messages}
        assert "human_3" in out_ids

    def test_summarizer_no_summarization_when_all_fit_in_tail(self, mock_model):
        """Test that no summarization occurs when all messages fit in tail."""
        messages = [
            HumanMessage(content="Short question?", id="human_1"),
            AIMessage(content="Short answer.", id="ai_1"),
        ]

        summarizer = ConversationSummarizer(
            model=mock_model,
            tail_token_budget=100,  # Large budget to fit all messages
            summary_max_tokens=100,
        )

        context = {}
        result = summarizer.summarize(messages, context)

        # Should not have called the model (no summarization needed)
        mock_model.invoke.assert_not_called()

        # Should return empty result (no changes needed)
        assert result == {}

    def test_summarizer_handles_empty_messages(self, mock_model):
        """Test summarizer handles empty message list."""
        summarizer = ConversationSummarizer(
            model=mock_model,
            tail_token_budget=100,
            summary_max_tokens=100,
        )

        context = {}
        result = summarizer.summarize([], context)

        # Should not have called the model
        mock_model.invoke.assert_not_called()

        # Should return empty result
        assert result == {}

    def test_summarizer_creates_proper_output_structure(self, mock_model):
        """Test that summarizer creates the correct output structure."""
        messages = [
            HumanMessage(content="Test question?", id="human_1"),
            AIMessage(content="Test answer.", id="ai_1"),
            HumanMessage(content="Follow up?", id="human_2"),
            AIMessage(content="Follow up answer.", id="ai_2"),
        ]

        summarizer = ConversationSummarizer(
            model=mock_model,
            tail_token_budget=0,
            summary_max_tokens=100,
        )

        context = {"existing_key": "existing_value"}
        result = summarizer.summarize(messages, context)

        # Should have called the model
        mock_model.invoke.assert_called_once()

        # Should have messages and context
        assert "messages" in result
        assert "context" in result

        # Context should preserve existing keys and add running_summary
        assert result["context"]["existing_key"] == "existing_value"
        assert "running_summary" in result["context"]

        # Messages should include summary system message
        output_messages = result["messages"]
        system_messages = [msg for msg in output_messages if isinstance(msg, SystemMessage)]
        assert len(system_messages) >= 1

        summary_msg = system_messages[0]
        assert summary_msg.content.startswith("Summary of the conversation so far:")

    def test_default_include_predicate(self):
        """Test the default include predicate logic."""
        summarizer = ConversationSummarizer(
            model=MagicMock(),
            tail_token_budget=100,
            summary_max_tokens=100,
        )

        # Test conversational messages (should include)
        human_msg = HumanMessage(content="Hello")
        ai_msg = AIMessage(content="Hi there")

        assert summarizer.include_in_summary(human_msg) is True
        assert summarizer.include_in_tail(ai_msg) is True

        # Test injected context (should exclude)
        context_msg = AIMessage(content="CONTEXT_PROFILE: name=Rick; city=Los Angeles;")
        assert summarizer.include_in_summary(context_msg) is False

        # Test memory injection (should exclude)
        memory_msg = AIMessage(content="Relevant context for tailoring this turn: ...")
        assert summarizer.include_in_summary(memory_msg) is False

        # Test handoff marker (should exclude)
        handoff_msg = AIMessage(
            content="Returning control",
            response_metadata={"is_handoff_back": True}
        )
        assert summarizer.include_in_summary(handoff_msg) is False

        # Test system message (should exclude)
        system_msg = SystemMessage(content="System message")
        assert summarizer.include_in_summary(system_msg) is False

    def test_tail_excludes_injected_context_and_handoff(self, mock_model):
        summarizer = ConversationSummarizer(
            model=mock_model,
            tail_token_budget=0,
            summary_max_tokens=64,
        )
        messages = [
            HumanMessage(content="Q1", id="h1"),
            AIMessage(content="A1", id="a1"),
            AIMessage(content="CONTEXT_PROFILE: name=Rick; city=LA", id="ctx1"),
            AIMessage(content="Returning control", response_metadata={"is_handoff_back": True}, id="handoff1"),
            HumanMessage(content="Q2", id="h2"),
            AIMessage(content="A2", id="a2"),
        ]
        out = summarizer.summarize(messages, {})
        out_ids = {getattr(m, "id", None) for m in out["messages"]}
        assert "ctx1" not in out_ids
        assert "handoff1" not in out_ids
        assert "h2" in out_ids

    def test_running_summary_last_id_is_last_head_included(self, mock_model):
        summarizer = ConversationSummarizer(
            model=mock_model,
            tail_token_budget=0,
            summary_max_tokens=64,
        )
        messages = [
            HumanMessage(content="Question number one is very long", id="h1"),  # ~6 tokens
            AIMessage(content="Answer number one is also very long response", id="a1"),  # ~8 tokens
            HumanMessage(content="Q2", id="h2"),
            AIMessage(content="A2", id="a2"),
        ]
        out = summarizer.summarize(messages, {})
        rs = out["context"]["running_summary"]
        assert rs.last_summarized_message_id == "a1"
        assert "h1" in rs.summarized_message_ids and "a1" in rs.summarized_message_ids

    def test_model_failure_raises(self):
        class FailingModel:
            def invoke(self, _):
                raise RuntimeError("boom")
        summarizer = ConversationSummarizer(
            model=FailingModel(),
            tail_token_budget=0,
            summary_max_tokens=64,
        )
        messages = [
            HumanMessage(content="Q1", id="h1"),
            AIMessage(content="A1", id="a1"),
            HumanMessage(content="Q2", id="h2"),
            AIMessage(content="A2", id="a2"),
        ]
        with pytest.raises(RuntimeError):
            summarizer.summarize(messages, {})

    def test_empty_summary_returns_no_change(self):
        class EmptyModel:
            class R:
                content = ""
            def invoke(self, _):
                return EmptyModel.R()
        summarizer = ConversationSummarizer(
            model=EmptyModel(),
            tail_token_budget=0,
            summary_max_tokens=64,
        )
        messages = [
            HumanMessage(content="Q1", id="h1"),
            AIMessage(content="A1", id="a1"),
            HumanMessage(content="Q2", id="h2"),
            AIMessage(content="A2", id="a2"),
        ]
        out = summarizer.summarize(messages, {})
        assert out == {}

    def test_noop_when_only_injected_messages(self, mock_model):
        summarizer = ConversationSummarizer(model=mock_model, tail_token_budget=0, summary_max_tokens=64)
        messages = [
            AIMessage(content="CONTEXT_PROFILE: name=Rick; city=LA", id="ctx1"),
            AIMessage(content="Relevant context for tailoring this turn: ...", id="mem1"),
        ]
        out = summarizer.summarize(messages, {})
        assert out == {}

    def test_custom_include_predicates_are_respected(self, mock_model):
        def include_summary(msg):
            return True  # include all in summary
        def include_tail(msg):
            return isinstance(msg, HumanMessage)  # keep only human messages in tail
        summarizer = ConversationSummarizer(
            model=mock_model,
            tail_token_budget=0,
            summary_max_tokens=64,
            include_in_summary=include_summary,
            include_in_tail=include_tail,
        )
        messages = [
            SystemMessage(content="sys", id="s1"),
            HumanMessage(content="Q1", id="h1"),
            AIMessage(content="A1", id="a1"),
            HumanMessage(content="Q2", id="h2"),
        ]
        out = summarizer.summarize(messages, {})
        out_ids = [getattr(m, "id", None) for m in out["messages"]]
        assert "h2" in out_ids and "a1" not in out_ids

    def test_tail_order_is_chronological(self, mock_model):
        summarizer = ConversationSummarizer(
            model=mock_model,
            tail_token_budget=0,
            summary_max_tokens=64,
        )
        messages = [
            HumanMessage(content="First question that is quite long and detailed and takes many tokens", id="h1"),  # ~12 tokens
            AIMessage(content="First answer that is also quite long and detailed and takes many tokens", id="a1"),  # ~12 tokens
            HumanMessage(content="Q2", id="h2"),  # ~1 token
            AIMessage(content="A2", id="a2"),  # ~1 token
        ]
        out = summarizer.summarize(messages, {})
        out_ids = [getattr(m, "id", None) for m in out.get("messages", [])]
        assert "h2" in out_ids
        assert out_ids[-1] == "a2"

    def test_system_message_in_head_is_removed_post_summary(self, mock_model):
        summarizer = ConversationSummarizer(
            model=mock_model,
            tail_token_budget=0,
            summary_max_tokens=64,
        )
        messages = [
            SystemMessage(content="System banner", id="sys1"),
            HumanMessage(content="Hello", id="h1"),
            AIMessage(content="Hi", id="a1"),
            HumanMessage(content="New", id="h2"),
            AIMessage(content="Ok", id="a2"),
        ]
        out = summarizer.summarize(messages, {})
        out_ids = [getattr(m, "id", None) for m in out["messages"]]
        assert "sys1" not in out_ids

    def test_block_content_is_normalized(self):
        class BlockModel:
            class R:
                content = [{"type": "text", "text": "- Bullet 1"}, {"type": "text", "text": "- Bullet 2"}]
            def invoke(self, _):
                return BlockModel.R()
        summarizer = ConversationSummarizer(
            model=BlockModel(),
            tail_token_budget=0,
            summary_max_tokens=64,
        )
        messages = [
            HumanMessage(content="This is a very long question that exceeds the token budget", id="h1"),
            AIMessage(content="This is a very long answer that also exceeds the token budget", id="a1"),
            HumanMessage(content="Another question", id="h2"),
            AIMessage(content="Another answer", id="a2"),
        ]
        out = summarizer.summarize(messages, {})
        # Should have summary message
        system_msgs = [m for m in out["messages"] if isinstance(m, SystemMessage)]
        assert system_msgs and "Bullet 1" in system_msgs[0].content

    def test_messages_without_ids_do_not_break(self, mock_model):
        summarizer = ConversationSummarizer(
            model=mock_model,
            tail_token_budget=0,
            summary_max_tokens=64,
        )
        messages = [
            HumanMessage(content="This is a very long question without an ID that exceeds the token budget"),
            AIMessage(content="This is a very long answer without an ID that also exceeds the token budget"),
            HumanMessage(content="Second question without ID"),
            AIMessage(content="Second answer without ID"),
        ]
        out = summarizer.summarize(messages, {})
        # running_summary should exist with empty ids set
        rs = out["context"]["running_summary"]
        assert isinstance(rs.summarized_message_ids, set)
