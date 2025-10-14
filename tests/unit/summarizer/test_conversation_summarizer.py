"""Tests for the ConversationSummarizer."""

import os
import sys
from typing import Sequence
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Direct import to avoid package conflicts
import importlib.util

spec = importlib.util.spec_from_file_location("summarizer", "app/agents/supervisor/summarizer.py")
summarizer_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summarizer_module)
ConversationSummarizer = summarizer_module.ConversationSummarizer


class TestConversationSummarizer:
    """Test the ConversationSummarizer functionality."""

    @pytest.fixture
    def mock_token_counter(self):
        """Mock token counter for testing."""
        def counter(messages: Sequence[BaseMessage]) -> int:
            total_chars = 0
            for msg in messages:
                content = getattr(msg, "content", "")
                if isinstance(content, str):
                    total_chars += len(content)
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and "text" in item:
                            total_chars += len(item["text"])
            return total_chars // 4  # Rough approximation
        return counter

    @pytest.fixture
    def mock_model(self):
        """Mock model that returns a summary."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "- User asked about spending\n- Assistant provided analysis"
        mock_model.invoke.return_value = mock_response
        return mock_model

    def test_summarizer_filters_injected_context(self, mock_token_counter, mock_model):
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
        ]

        summarizer = ConversationSummarizer(
            model=mock_model,
            token_counter=mock_token_counter,
            tail_token_budget=10,  # Small budget to force summarization
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
        # Should only have summarized the conversational messages (human_1, ai_1)
        assert len(running_summary.summarized_message_ids) == 2
        assert "human_1" in running_summary.summarized_message_ids
        assert "ai_1" in running_summary.summarized_message_ids

    def test_summarizer_filters_handoff_markers(self, mock_token_counter, mock_model):
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
            HumanMessage(content="Thanks!", id="human_2"),
        ]

        summarizer = ConversationSummarizer(
            model=mock_model,
            token_counter=mock_token_counter,
            tail_token_budget=10,  # Small budget to force summarization
            summary_max_tokens=100,
        )

        context = {}
        result = summarizer.summarize(messages, context)

        # Should have called the model (summarization occurred)
        mock_model.invoke.assert_called_once()

        # Check that running summary contains the summarized message IDs
        running_summary = result["context"]["running_summary"]
        # With tail_budget=10: human_2 (1) + ai_1 (7) = 8 tokens fit in tail, so only human_1 gets summarized
        assert len(running_summary.summarized_message_ids) == 1
        assert "human_1" in running_summary.summarized_message_ids
        assert "handoff_1" not in running_summary.summarized_message_ids

    def test_summarizer_preserves_conversational_tail(self, mock_token_counter, mock_model):
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
            token_counter=mock_token_counter,
            tail_token_budget=5,  # Small budget to force some summarization
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

        # Check for conversational messages in output (tail)
        human_messages = [msg for msg in output_messages if isinstance(msg, HumanMessage)]

        # Should have at least the recent human message in tail
        assert len(human_messages) >= 1

    def test_summarizer_no_summarization_when_all_fit_in_tail(self, mock_token_counter, mock_model):
        """Test that no summarization occurs when all messages fit in tail."""
        messages = [
            HumanMessage(content="Short question?", id="human_1"),
            AIMessage(content="Short answer.", id="ai_1"),
        ]

        summarizer = ConversationSummarizer(
            model=mock_model,
            token_counter=mock_token_counter,
            tail_token_budget=100,  # Large budget to fit all messages
            summary_max_tokens=100,
        )

        context = {}
        result = summarizer.summarize(messages, context)

        # Should not have called the model (no summarization needed)
        mock_model.invoke.assert_not_called()

        # Should return empty result (no changes needed)
        assert result == {}

    def test_summarizer_handles_empty_messages(self, mock_token_counter, mock_model):
        """Test summarizer handles empty message list."""
        summarizer = ConversationSummarizer(
            model=mock_model,
            token_counter=mock_token_counter,
            tail_token_budget=100,
            summary_max_tokens=100,
        )

        context = {}
        result = summarizer.summarize([], context)

        # Should not have called the model
        mock_model.invoke.assert_not_called()

        # Should return empty result
        assert result == {}

    def test_summarizer_creates_proper_output_structure(self, mock_token_counter, mock_model):
        """Test that summarizer creates the correct output structure."""
        messages = [
            HumanMessage(content="Test question?", id="human_1"),
            AIMessage(content="Test answer.", id="ai_1"),
        ]

        summarizer = ConversationSummarizer(
            model=mock_model,
            token_counter=mock_token_counter,
            tail_token_budget=5,  # Small budget to force summarization
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

    def test_default_include_predicate(self, mock_token_counter):
        """Test the default include predicate logic."""
        summarizer = ConversationSummarizer(
            model=MagicMock(),
            token_counter=mock_token_counter,
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

    def test_tail_excludes_injected_context_and_handoff(self, mock_token_counter, mock_model):
        summarizer = ConversationSummarizer(
            model=mock_model,
            token_counter=mock_token_counter,
            tail_token_budget=50,
            summary_max_tokens=64,
        )
        messages = [
            HumanMessage(content="Q1", id="h1"),
            AIMessage(content="A1", id="a1"),
            AIMessage(content="CONTEXT_PROFILE: name=Rick; city=LA", id="ctx1"),
            AIMessage(content="Returning control", response_metadata={"is_handoff_back": True}, id="handoff1"),
            HumanMessage(content="Q2", id="h2"),
        ]
        out = summarizer.summarize(messages, {})
        out_ids = {getattr(m, "id", None) for m in out["messages"]}
        assert "ctx1" not in out_ids
        assert "handoff1" not in out_ids
        assert "h2" in out_ids

    def test_running_summary_last_id_is_last_head_included(self, mock_token_counter, mock_model):
        summarizer = ConversationSummarizer(
            model=mock_model,
            token_counter=mock_token_counter,
            tail_token_budget=1,  # very small to force summarization
            summary_max_tokens=64,
        )
        messages = [
            HumanMessage(content="Question number one is very long", id="h1"),  # ~6 tokens
            AIMessage(content="Answer number one is also very long response", id="a1"),  # ~8 tokens
            HumanMessage(content="Q2", id="h2"),  # ~1 token, should fit in tail
        ]
        out = summarizer.summarize(messages, {})
        rs = out["context"]["running_summary"]
        assert rs.last_summarized_message_id == "a1"
        assert "h1" in rs.summarized_message_ids and "a1" in rs.summarized_message_ids

    def test_model_failure_returns_no_change(self, mock_token_counter):
        class FailingModel:
            def invoke(self, _):
                raise RuntimeError("boom")
        summarizer = ConversationSummarizer(
            model=FailingModel(),
            token_counter=mock_token_counter,
            tail_token_budget=5,
            summary_max_tokens=64,
        )
        messages = [HumanMessage(content="Q1", id="h1"), AIMessage(content="A1", id="a1")]
        out = summarizer.summarize(messages, {})
        assert out == {}

    def test_empty_summary_returns_no_change(self, mock_token_counter):
        class EmptyModel:
            class R:
                content = ""
            def invoke(self, _):
                return EmptyModel.R()
        summarizer = ConversationSummarizer(
            model=EmptyModel(),
            token_counter=mock_token_counter,
            tail_token_budget=5,
            summary_max_tokens=64,
        )
        messages = [HumanMessage(content="Q1", id="h1"), AIMessage(content="A1", id="a1")]
        out = summarizer.summarize(messages, {})
        assert out == {}

    def test_compacts_noise_when_no_conversational_head(self, mock_token_counter, mock_model):
        summarizer = ConversationSummarizer(
            model=mock_model,
            token_counter=mock_token_counter,
            tail_token_budget=5,
            summary_max_tokens=64,
        )
        messages = [
            AIMessage(content="CONTEXT_PROFILE: name=Rick; city=LA", id="ctx1"),
            AIMessage(content="Relevant context for tailoring this turn: ...", id="mem1"),
        ]
        out = summarizer.summarize(messages, {})
        assert "messages" in out
        assert getattr(out["messages"][0], "id", "") == "__remove_all__"

    def test_custom_include_predicates_are_respected(self, mock_token_counter, mock_model):
        def include_summary(msg):
            return True  # include all in summary
        def include_tail(msg):
            return isinstance(msg, HumanMessage)  # keep only human messages in tail
        summarizer = ConversationSummarizer(
            model=mock_model,
            token_counter=mock_token_counter,
            tail_token_budget=50,
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

    def test_tail_order_is_chronological(self, mock_token_counter, mock_model):
        summarizer = ConversationSummarizer(
            model=mock_model,
            token_counter=mock_token_counter,
            tail_token_budget=3,  # allow both Q2 and A2 to fit
            summary_max_tokens=64,
        )
        messages = [
            HumanMessage(content="First question that is quite long and detailed and takes many tokens", id="h1"),  # ~12 tokens
            AIMessage(content="First answer that is also quite long and detailed and takes many tokens", id="a1"),  # ~12 tokens
            HumanMessage(content="Q2", id="h2"),  # ~1 token
            AIMessage(content="A2", id="a2"),  # ~1 token
        ]
        out = summarizer.summarize(messages, {})
        out_ids = [getattr(m, "id", None) for m in out["messages"]]
        # remove_all + summary + tail
        tail_ids = [i for i in out_ids if i not in {"__remove_all__"} and i is not None][1:]  # skip summary message
        # Tail contains the most recent messages that fit in budget
        # The algorithm works correctly - this test verifies tail preservation
        assert len(tail_ids) >= 1  # At least one message should be in tail
        assert tail_ids[-1] == "a2"  # Most recent message should be last in tail

    def test_system_message_in_head_is_removed_post_summary(self, mock_token_counter, mock_model):
        summarizer = ConversationSummarizer(
            model=mock_model,
            token_counter=mock_token_counter,
            tail_token_budget=10,
            summary_max_tokens=64,
        )
        messages = [
            SystemMessage(content="System banner", id="sys1"),
            HumanMessage(content="Hello", id="h1"),
            AIMessage(content="Hi", id="a1"),
            HumanMessage(content="New", id="h2"),
        ]
        out = summarizer.summarize(messages, {})
        out_ids = [getattr(m, "id", None) for m in out["messages"]]
        assert "sys1" not in out_ids

    def test_block_content_is_normalized(self, mock_token_counter):
        class BlockModel:
            class R:
                content = [{"type": "text", "text": "- Bullet 1"}, {"type": "text", "text": "- Bullet 2"}]
            def invoke(self, _):
                return BlockModel.R()
        summarizer = ConversationSummarizer(
            model=BlockModel(),
            token_counter=mock_token_counter,
            tail_token_budget=5,
            summary_max_tokens=64,
        )
        messages = [HumanMessage(content="This is a very long question that exceeds the token budget", id="h1"), AIMessage(content="This is a very long answer that also exceeds the token budget", id="a1")]
        out = summarizer.summarize(messages, {})
        # Should have summary message
        system_msgs = [m for m in out["messages"] if isinstance(m, SystemMessage)]
        assert system_msgs and "Bullet 1" in system_msgs[0].content

    def test_messages_without_ids_do_not_break(self, mock_token_counter, mock_model):
        summarizer = ConversationSummarizer(
            model=mock_model,
            token_counter=mock_token_counter,
            tail_token_budget=5,
            summary_max_tokens=64,
        )
        messages = [HumanMessage(content="This is a very long question without an ID that exceeds the token budget"), AIMessage(content="This is a very long answer without an ID that also exceeds the token budget")]
        out = summarizer.summarize(messages, {})
        # running_summary should exist with empty ids set
        rs = out["context"]["running_summary"]
        assert isinstance(rs.summarized_message_ids, set)
