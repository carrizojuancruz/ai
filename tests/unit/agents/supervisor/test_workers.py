"""Tests for app/agents/supervisor/workers.py"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import MessagesState

from app.agents.supervisor.finance_agent.tools import PLAID_REQUIRED_STATUS_PREFIX
from app.agents.supervisor.workers import (
    finance_router,
    goal_agent,
    wealth_agent,
    wealth_router,
)


def extract_message_content(messages_or_result):
    """Extract content from the first message in a messages array or result dict."""
    if isinstance(messages_or_result, dict) and "messages" in messages_or_result:
        messages = messages_or_result["messages"]
    else:
        messages = messages_or_result

    if not messages:
        return ""

    first_message = messages[0]
    return str(first_message.get("content") if isinstance(first_message, dict) else first_message.content)


@pytest.mark.unit
class TestWealthAgent:
    """Test suite for wealth_agent worker function."""

    @pytest.mark.asyncio
    async def test_wealth_agent_successful_response(
        self, mock_wealth_agent_graph, mock_config
    ):
        """Test wealth_agent returns successful response."""
        state = MessagesState(
            messages=[HumanMessage(content="What is an emergency fund?")]
        )

        result = await wealth_agent(state, mock_config)

        assert "messages" in result
        assert len(result["messages"]) > 0

    @pytest.mark.asyncio
    async def test_wealth_agent_invokes_graph(
        self, mock_wealth_agent_graph, mock_config
    ):
        """Test that wealth_agent invokes the wealth agent graph."""
        state = MessagesState(messages=[HumanMessage(content="Test question")])

        await wealth_agent(state, mock_config)

        mock_wealth_agent_graph.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_wealth_agent_extracts_response_correctly(
        self, mock_wealth_agent_graph, mock_config
    ):
        """Test that wealth_agent extracts the correct response."""
        mock_wealth_agent_graph.ainvoke.return_value = {
            "messages": [
                AIMessage(
                    content="An emergency fund is savings for unexpected expenses.",
                    name="wealth_agent",
                )
            ]
        }

        state = MessagesState(messages=[HumanMessage(content="Test")])
        result = await wealth_agent(state, mock_config)

        assert any(
            "emergency fund" in msg.get("content", "").lower()
            if isinstance(msg, dict)
            else "emergency fund" in str(msg.content).lower()
            for msg in result["messages"]
        )

    @pytest.mark.asyncio
    async def test_wealth_agent_returns_handoff_messages(
        self, mock_wealth_agent_graph, mock_config
    ):
        """Test that wealth_agent returns handoff messages."""
        state = MessagesState(messages=[HumanMessage(content="Test")])

        result = await wealth_agent(state, mock_config)

        assert len(result["messages"]) >= 1

    @pytest.mark.asyncio
    async def test_wealth_agent_handles_errors(self, mock_wealth_agent_graph, mock_config):
        """Test that wealth_agent handles errors gracefully."""
        mock_wealth_agent_graph.ainvoke.side_effect = Exception("Graph error")

        state = MessagesState(messages=[HumanMessage(content="Test")])
        result = await wealth_agent(state, mock_config)

        assert "messages" in result
        messages = result["messages"]
        assert len(messages) > 0
        content = extract_message_content(result)
        assert "problem" in content.lower() or "sorry" in content.lower()

    @pytest.mark.asyncio
    async def test_wealth_agent_uses_unique_thread_id(
        self, mock_wealth_agent_graph, mock_config
    ):
        """Test that wealth_agent uses a unique thread ID."""
        state = MessagesState(messages=[HumanMessage(content="Test")])

        await wealth_agent(state, mock_config)

        call_args = mock_wealth_agent_graph.ainvoke.call_args
        config = call_args[1]["config"]
        assert "configurable" in config
        assert "thread_id" in config["configurable"]
        assert config["configurable"]["thread_id"].startswith("wealth-task-")

    @pytest.mark.asyncio
    async def test_wealth_agent_passes_user_id(
        self, mock_wealth_agent_graph, mock_config
    ):
        """Test that wealth_agent passes user_id to subgraph."""
        state = MessagesState(messages=[HumanMessage(content="Test")])

        await wealth_agent(state, mock_config)

        call_args = mock_wealth_agent_graph.ainvoke.call_args
        config = call_args[1]["config"]
        assert "user_id" in config["configurable"]

    @pytest.mark.asyncio
    async def test_wealth_agent_handles_empty_response(
        self, mock_wealth_agent_graph, mock_config
    ):
        """Test wealth_agent handles empty response from graph."""
        mock_wealth_agent_graph.ainvoke.return_value = {"messages": []}

        state = MessagesState(messages=[HumanMessage(content="Test")])
        result = await wealth_agent(state, mock_config)

        assert len(result["messages"]) > 0


@pytest.mark.unit
class TestGoalAgent:
    """Test suite for goal_agent worker function."""

    @pytest.mark.asyncio
    async def test_goal_agent_successful_response(
        self, mock_goal_agent_graph, mock_config
    ):
        """Test goal_agent returns successful response."""
        state = MessagesState(
            messages=[HumanMessage(content="How is my savings goal?")]
        )

        result = await goal_agent(state, mock_config)

        assert "messages" in result
        assert len(result["messages"]) > 0

    @pytest.mark.asyncio
    async def test_goal_agent_invokes_graph(
        self, mock_goal_agent_graph, mock_config
    ):
        """Test that goal_agent invokes the goal agent graph."""
        state = MessagesState(messages=[HumanMessage(content="Test")])

        await goal_agent(state, mock_config)

        mock_goal_agent_graph.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_goal_agent_extracts_response_correctly(
        self, mock_goal_agent_graph, mock_config
    ):
        """Test that goal_agent extracts the correct response."""
        state = MessagesState(messages=[HumanMessage(content="Test")])
        result = await goal_agent(state, mock_config)

        messages = result["messages"]
        assert len(messages) > 0

    @pytest.mark.asyncio
    async def test_goal_agent_handles_errors(
        self, mock_goal_agent_graph, mock_config
    ):
        """Test that goal_agent handles errors gracefully."""
        mock_goal_agent_graph.ainvoke.side_effect = Exception("Goal error")

        state = MessagesState(messages=[HumanMessage(content="Test")])
        result = await goal_agent(state, mock_config)

        assert "messages" in result
        content = extract_message_content(result)
        assert "problem" in content.lower() or "sorry" in content.lower()

    @pytest.mark.asyncio
    async def test_goal_agent_uses_unique_thread_id(
        self, mock_goal_agent_graph, mock_config
    ):
        """Test that goal_agent uses a unique thread ID."""
        state = MessagesState(messages=[HumanMessage(content="Test")])

        await goal_agent(state, mock_config)

        call_args = mock_goal_agent_graph.ainvoke.call_args
        config = call_args[1]["config"]
        assert config["configurable"]["thread_id"].startswith("goal-task-")

    @pytest.mark.asyncio
    async def test_goal_agent_passes_user_id(
        self, mock_goal_agent_graph, mock_config
    ):
        """Test that goal_agent passes user_id to subgraph."""
        state = MessagesState(messages=[HumanMessage(content="Test")])

        await goal_agent(state, mock_config)

        call_args = mock_goal_agent_graph.ainvoke.call_args
        config = call_args[1]["config"]
        assert "user_id" in config["configurable"]

    @pytest.mark.asyncio
    async def test_goal_agent_returns_default_on_empty_response(
        self, mock_goal_agent_graph, mock_config
    ):
        """Test goal_agent returns default message on empty response."""
        mock_goal_agent_graph.ainvoke.return_value = {"messages": []}

        state = MessagesState(messages=[HumanMessage(content="Test")])
        result = await goal_agent(state, mock_config)

        assert len(result["messages"]) > 0


@pytest.mark.unit
class TestWealthRouter:
    """Test suite for wealth_router function."""

    @pytest.mark.asyncio
    async def test_wealth_router_success(
        self, mock_wealth_agent_graph, mock_config
    ):
        """Test wealth_router successfully routes to wealth_agent."""
        state = MessagesState(messages=[HumanMessage(content="Test")])

        result = await wealth_router(state, mock_config)

        assert "messages" in result
        assert len(result["messages"]) > 0

    @pytest.mark.asyncio
    async def test_wealth_router_error_handling(
        self, mock_wealth_agent_graph, mock_config
    ):
        """Test wealth_router error handling."""
        mock_wealth_agent_graph.ainvoke.side_effect = Exception("Router error")

        state = MessagesState(messages=[HumanMessage(content="Test")])
        result = await wealth_router(state, mock_config)

        assert "messages" in result
        messages = result["messages"]
        assert len(messages) > 0
        content = extract_message_content(result)
        assert "problem" in content.lower() or "sorry" in content.lower()

    @pytest.mark.asyncio
    async def test_wealth_router_includes_agent_name(
        self, mock_wealth_agent_graph, mock_config
    ):
        """Test that wealth_router returns messages with wealth_agent name."""
        state = MessagesState(messages=[HumanMessage(content="Test")])

        result = await wealth_router(state, mock_config)

        messages = result["messages"]
        assert len(messages) > 0


@pytest.mark.unit
class TestFinanceRouter:
    """Test suite for finance_router function."""

    @pytest.mark.asyncio
    async def test_finance_router_with_accounts(
        self, mock_session_store, mock_finance_agent, mock_config
    ):
        """Test finance_router with connected accounts."""
        mock_session_store.get_session.reset_mock()
        mock_session_store.get_session.return_value = {
            "has_financial_accounts": True,
            "has_plaid_accounts": True,
            "has_financial_data": True,
        }
        mock_finance_agent.reset_mock()

        state = MessagesState(messages=[HumanMessage(content="What's my balance?")])

        await finance_router(state, mock_config)

        mock_finance_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_finance_router_without_accounts(
        self, mock_session_store, mock_finance_agent, mock_config
    ):
        """Test finance_router without connected accounts."""
        mock_session_store.get_session.return_value = {
            "has_financial_accounts": False,
            "has_financial_data": False,
        }

        state = MessagesState(messages=[HumanMessage(content="List my assets")])
        result = await finance_router(state, mock_config)

        mock_finance_agent.assert_called_once_with(state, mock_config)
        assert result == await mock_finance_agent(state, mock_config)

    @pytest.mark.asyncio
    async def test_finance_router_missing_thread_id(
        self, mock_session_store, mock_config_no_user
    ):
        """Test finance_router with missing thread_id."""
        config = {"configurable": {}}

        state = MessagesState(messages=[HumanMessage(content="Test")])
        result = await finance_router(state, config)

        content = extract_message_content(result)
        assert "NO_ACCOUNTS" in content or "THREAD ID" in content

    @pytest.mark.asyncio
    async def test_finance_router_session_store_error(
        self, mock_session_store, mock_config
    ):
        """Test finance_router handles session store errors."""
        mock_session_store.get_session.side_effect = Exception("Session error")

        state = MessagesState(messages=[HumanMessage(content="Test")])
        result = await finance_router(state, mock_config)

        content = str(result["messages"][0].get("content") if isinstance(result["messages"][0], dict) else result["messages"][0].content)
        assert "financial accounts" in content.lower() or "connect" in content.lower()

    @pytest.mark.asyncio
    async def test_finance_router_checks_session_for_accounts(
        self, mock_session_store, mock_finance_agent, mock_config
    ):
        """Test that finance_router checks session for financial accounts."""
        mock_session_store.get_session.reset_mock()
        mock_session_store.get_session.return_value = {
            "has_financial_accounts": True,
            "has_plaid_accounts": True,
            "has_financial_data": True,
        }

        state = MessagesState(messages=[HumanMessage(content="Test")])

        await finance_router(state, mock_config)

        mock_session_store.get_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_finance_router_returns_finance_agent_name(
        self, mock_session_store, mock_config_no_user
    ):
        """Test that finance_router returns messages with finance_agent name."""
        config = {"configurable": {}}

        state = MessagesState(messages=[HumanMessage(content="Test")])
        result = await finance_router(state, config)

        messages = result["messages"]
        msg = messages[0]
        if isinstance(msg, dict):
            assert msg.get("name") == "finance_agent"
        else:
            assert msg.name == "finance_agent"

    @pytest.mark.asyncio
    async def test_finance_router_with_none_session(
        self, mock_session_store, mock_finance_agent, mock_config
    ):
        """Test finance_router when session is None."""
        mock_session_store.get_session.return_value = None

        state = MessagesState(messages=[HumanMessage(content="List my assets")])
        result = await finance_router(state, mock_config)

        mock_finance_agent.assert_called_once_with(state, mock_config)
        assert result == await mock_finance_agent(state, mock_config)

    @pytest.mark.asyncio
    async def test_finance_router_delegates_to_finance_worker(
        self, mock_session_store, mock_finance_agent, mock_config
    ):
        """Test that finance_router delegates to finance_worker when accounts exist."""
        mock_session_store.get_session.reset_mock()
        mock_session_store.get_session.return_value = {
            "has_financial_accounts": True,
            "has_plaid_accounts": True,
            "has_financial_data": True,
        }
        mock_finance_agent.reset_mock()

        state = MessagesState(messages=[HumanMessage(content="Show spending")])

        result = await finance_router(state, mock_config)

        mock_finance_agent.assert_called_once_with(state, mock_config)

        assert result == await mock_finance_agent(state, mock_config)

    @pytest.mark.asyncio
    async def test_finance_router_adds_nav_event_when_plaid_required(
        self, mock_session_store, mock_finance_agent, mock_config
    ):
        """Test that finance_router appends navigation event when plaid data is needed."""
        mock_session_store.get_session.return_value = {
            "has_financial_accounts": False,
            "has_plaid_accounts": False,
            "has_financial_data": True,
        }
        sentinel_text = f"{PLAID_REQUIRED_STATUS_PREFIX} — Please connect"
        mock_finance_agent.return_value = {
            "messages": [{"role": "assistant", "content": sentinel_text, "name": "finance_agent"}]
        }

        state = MessagesState(messages=[HumanMessage(content="Show latest transactions")])
        result = await finance_router(state, mock_config)

        nav_events = result.get("navigation_events", [])
        assert any(event.get("event") == "navigation.connected-accounts" for event in nav_events)
