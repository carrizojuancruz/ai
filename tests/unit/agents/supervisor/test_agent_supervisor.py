"""Tests for app/agents/supervisor/agent.py token-based summarization gating helpers."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.supervisor.agent import (
    CONTEXT_KEY_MAX_PROMPT_TOKENS_LAST_RUN,
    count_user_messages_for_trigger,
    should_trigger_summarization_at_turn_start,
)


@pytest.mark.unit
class TestSummarizationGatingHelpers:
    def test_count_user_messages_ignores_injected_context(self) -> None:
        messages = [
            HumanMessage(content="CONTEXT_PROFILE: some profile"),
            HumanMessage(content="Relevant context for tailoring this turn: injected"),
            HumanMessage(content="Actual user question"),
            AIMessage(content="Assistant response"),
            HumanMessage(content="Second question"),
        ]
        assert count_user_messages_for_trigger(messages) == 2

    def test_should_trigger_by_prompt_tokens(self) -> None:
        messages = [HumanMessage(content="Hello")]
        context = {CONTEXT_KEY_MAX_PROMPT_TOKENS_LAST_RUN: 25_000}
        assert should_trigger_summarization_at_turn_start(
            messages=messages,
            context=context,
            trigger_prompt_tokens=25_000,
            fallback_user_message_count=20,
        )

    def test_should_trigger_by_fallback_user_count(self) -> None:
        messages = [HumanMessage(content=f"m{i}") for i in range(20)]
        context = {CONTEXT_KEY_MAX_PROMPT_TOKENS_LAST_RUN: 0}
        assert should_trigger_summarization_at_turn_start(
            messages=messages,
            context=context,
            trigger_prompt_tokens=25_000,
            fallback_user_message_count=20,
        )

    def test_should_not_trigger_when_below_both_thresholds(self) -> None:
        messages = [HumanMessage(content=f"m{i}") for i in range(3)]
        context = {CONTEXT_KEY_MAX_PROMPT_TOKENS_LAST_RUN: 0}
        assert not should_trigger_summarization_at_turn_start(
            messages=messages,
            context=context,
            trigger_prompt_tokens=25_000,
            fallback_user_message_count=20,
        )
