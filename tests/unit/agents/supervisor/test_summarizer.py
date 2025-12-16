"""Tests for app/agents/supervisor/summarizer.py"""

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage
from langmem.short_term import RunningSummary

from app.agents.supervisor.summarizer import ConversationSummarizer


@pytest.mark.unit
class TestConversationSummarizerInit:
    def test_init_with_required_params(self) -> None:
        mock_model = MagicMock()
        summarizer = ConversationSummarizer(model=mock_model)
        assert summarizer.model == mock_model
        assert summarizer.tail_token_budget == 3500

    def test_init_with_custom_tail_token_budget(self) -> None:
        summarizer = ConversationSummarizer(model=MagicMock(), tail_token_budget=123)
        assert summarizer.tail_token_budget == 123


@pytest.mark.unit
class TestConversationSummarizerSummarize:
    @pytest.fixture
    def mock_model(self):
        mock = MagicMock()
        mock.invoke.return_value = MagicMock(content="This is a concise summary of the conversation.")
        return mock

    def test_summarize_empty_messages_returns_empty_dict(self, mock_model) -> None:
        summarizer = ConversationSummarizer(model=mock_model, tail_token_budget=1)
        assert summarizer.summarize([], {}) == {}

    def test_summarize_noop_when_all_dialogue_fits_in_tail(self, mock_model) -> None:
        summarizer = ConversationSummarizer(model=mock_model, tail_token_budget=10_000)
        messages = [HumanMessage(content="hi"), AIMessage(content="hello")]
        assert summarizer.summarize(messages, {}) == {}

    def test_summarize_preserves_last_turn_when_budget_tiny(self, mock_model) -> None:
        summarizer = ConversationSummarizer(model=mock_model, tail_token_budget=0)
        messages = [
            HumanMessage(content="q1", id="u1"),
            AIMessage(content="a1", id="a1"),
            HumanMessage(content="q2", id="u2"),
            AIMessage(content="a2", id="a2"),
            HumanMessage(content="q3", id="u3"),
            AIMessage(content="a3", id="a3"),
        ]
        result = summarizer.summarize(messages, {})
        tail_messages = [m for m in result.get("messages", []) if not isinstance(m, (SystemMessage, RemoveMessage))]
        assert [getattr(m, "content", "") for m in tail_messages] == ["q3", "a3"]

    def test_summarize_with_small_positive_budget_keeps_at_least_last_turn(self, mock_model) -> None:
        summarizer = ConversationSummarizer(model=mock_model, tail_token_budget=1)
        long_text = "x" * 500  # > 1 estimated token for sure
        messages = [
            HumanMessage(content="q1", id="u1"),
            AIMessage(content="a1", id="a1"),
            HumanMessage(content=long_text, id="u2"),
            AIMessage(content=long_text, id="a2"),
        ]
        result = summarizer.summarize(messages, {})
        tail_messages = [m for m in result.get("messages", []) if not isinstance(m, (SystemMessage, RemoveMessage))]
        assert [getattr(m, "content", "") for m in tail_messages] == [long_text, long_text]

    def test_summarize_creates_system_summary_and_running_summary(self, mock_model) -> None:
        summarizer = ConversationSummarizer(model=mock_model, tail_token_budget=0)
        messages = [
            HumanMessage(content="q1", id="u1"),
            AIMessage(content="a1", id="a1"),
            HumanMessage(content="q2", id="u2"),
            AIMessage(content="a2", id="a2"),
        ]
        result = summarizer.summarize(messages, {})
        msgs = result.get("messages", [])
        assert any(isinstance(m, SystemMessage) for m in msgs)
        assert isinstance(result.get("context", {}).get("running_summary"), RunningSummary)

    def test_summarize_transcript_deduplicates_consecutive_duplicates(self, mock_model) -> None:
        summarizer = ConversationSummarizer(model=mock_model, tail_token_budget=0)
        messages = [
            HumanMessage(content="q1", id="u1"),
            AIMessage(content="a1", id="a1"),
            AIMessage(content="a1", id="a1_dup"),
            HumanMessage(content="q2", id="u2"),
            AIMessage(content="a2", id="a2"),
        ]
        summarizer.summarize(messages, {})
        invoke_messages = summarizer.model.invoke.call_args[0][0]
        transcript = str(getattr(invoke_messages[1], "content", ""))
        assert transcript.count("Assistant: a1") == 1

    def test_summarize_filters_handoff_messages(self, mock_model) -> None:
        summarizer = ConversationSummarizer(model=mock_model, tail_token_budget=0)
        messages = [
            HumanMessage(content="User question", id="msg_1"),
            AIMessage(content="Returning control to supervisor", id="msg_2", response_metadata={"is_handoff_back": True}),
            AIMessage(content="Regular response", id="msg_3"),
            HumanMessage(content="Follow up question", id="msg_4"),
            AIMessage(content="Second response", id="msg_5"),
        ]
        summarizer.summarize(messages, {})
        invoke_messages = summarizer.model.invoke.call_args[0][0]
        assert "Returning control to supervisor" not in str(getattr(invoke_messages[1], "content", ""))

    def test_summarize_excludes_injected_and_subagent_artifacts(self, mock_model) -> None:
        summarizer = ConversationSummarizer(model=mock_model, tail_token_budget=0)
        messages = [
            HumanMessage(content="CONTEXT_PROFILE: user info", id="c1"),
            HumanMessage(content="q1", id="u1"),
            AIMessage(content="a1", id="a1"),
            AIMessage(content="===== GOAL AGENT TASK COMPLETED =====", name="goal_agent", id="ga1"),
            HumanMessage(content="q2", id="u2"),
            AIMessage(content="a2", id="a2"),
        ]
        summarizer.summarize(messages, {})
        invoke_messages = summarizer.model.invoke.call_args[0][0]
        transcript = str(getattr(invoke_messages[1], "content", ""))
        assert "CONTEXT_PROFILE" not in transcript
        assert "GOAL AGENT TASK COMPLETED" not in transcript


@pytest.mark.unit
class TestConversationSummarizerAsNode:
    def test_as_node_returns_callable(self) -> None:
        mock_model = MagicMock()
        mock_model.invoke.return_value = MagicMock(content="Summary text")
        summarizer = ConversationSummarizer(model=mock_model, tail_token_budget=0)
        node = summarizer.as_node()
        assert callable(node)
