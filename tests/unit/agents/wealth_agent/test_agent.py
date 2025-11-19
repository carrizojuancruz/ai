"""Tests for app/agents/supervisor/wealth_agent/agent.py"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from app.agents.supervisor.wealth_agent.agent import (
    WealthAgent,
    compile_wealth_agent_graph,
    wealth_agent,
)


@pytest.mark.unit
class TestWealthAgent:
    """Test suite for WealthAgent class."""

    def test_wealth_agent_initialization(self, mock_llm, mocker):
        """Test WealthAgent initializes correctly."""
        mocker.patch("app.agents.supervisor.wealth_agent.agent.ChatCerebras", return_value=mock_llm)

        agent = WealthAgent()

        assert agent is not None
        assert hasattr(agent, "llm")

    def test_wealth_agent_has_correct_llm_config(self, mock_llm, mocker):
        """Test WealthAgent configures LLM with correct parameters."""
        mock_llm_class = mocker.patch("app.agents.supervisor.wealth_agent.agent.ChatCerebras")
        mock_llm_class.return_value = mock_llm

        WealthAgent()

        mock_llm_class.assert_called_once()
        call_kwargs = mock_llm_class.call_args[1]

        assert "model" in call_kwargs
        assert "api_key" in call_kwargs
        assert "temperature" in call_kwargs

    def test_create_system_prompt(self, mock_wealth_agent_instance):
        """Test _create_system_prompt generates prompt."""
        prompt = mock_wealth_agent_instance._create_system_prompt()

        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "Wealth" in prompt or "wealth" in prompt

    def test_create_system_prompt_with_user_context(self, mock_wealth_agent_instance):
        """Test _create_system_prompt includes user context."""
        user_context = {
            "location": "New York",
            "financial_situation": "Looking to invest",
        }

        prompt = mock_wealth_agent_instance._create_system_prompt(user_context)

        assert "New York" in prompt or "location" in prompt.lower()

    @pytest.mark.asyncio
    async def test_process_query_with_agent_success(self, mock_wealth_agent_instance, mocker):
        """Test process_query_with_agent successfully processes query."""
        user_id = uuid4()
        query = "What is an emergency fund?"

        mock_graph = MagicMock()
        mock_command = Command(
            update={"messages": [{"role": "assistant", "content": "Response"}]},
            goto="supervisor"
        )
        mock_graph.ainvoke = AsyncMock(return_value=mock_command)

        mocker.patch.object(mock_wealth_agent_instance, "_create_agent_with_tools", return_value=mock_graph)

        result = await mock_wealth_agent_instance.process_query_with_agent(query, user_id)

        assert isinstance(result, Command)
        mock_graph.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_query_with_agent_handles_error(self, mock_wealth_agent_instance, mocker):
        """Test process_query_with_agent handles errors gracefully."""
        user_id = uuid4()
        query = "Test query"

        mocker.patch.object(
            mock_wealth_agent_instance,
            "_create_agent_with_tools",
            side_effect=Exception("Graph error")
        )

        result = await mock_wealth_agent_instance.process_query_with_agent(query, user_id)

        assert isinstance(result, Command)
        assert "error" in str(result).lower() or "problem" in str(result).lower()


@pytest.mark.unit
class TestCompileWealthAgentGraph:
    """Test suite for compile_wealth_agent_graph function."""

    def test_compile_creates_wealth_agent(self, mock_llm, mocker):
        """Test compile_wealth_agent_graph creates WealthAgent instance."""
        mock_wealth_class = mocker.patch("app.agents.supervisor.wealth_agent.agent.WealthAgent")
        mocker.patch("app.agents.supervisor.wealth_agent.agent.ChatCerebras", return_value=mock_llm)

        compile_wealth_agent_graph()

        mock_wealth_class.assert_called_once()


@pytest.mark.unit
class TestWealthAgentWorker:
    """Test suite for wealth_agent worker function."""

    @pytest.mark.asyncio
    async def test_wealth_agent_worker_success(self, mock_config, mocker):
        """Test wealth_agent worker processes request successfully."""
        state = {"messages": [HumanMessage(content="Test query")]}

        mock_instance = MagicMock()
        mock_command = Command(
            update={"messages": [{"role": "assistant", "content": "Response"}]},
            goto="supervisor"
        )
        mock_instance.process_query_with_agent = AsyncMock(return_value=mock_command)

        mocker.patch("app.agents.supervisor.wealth_agent.agent.get_wealth_agent", return_value=mock_instance)

        result = await wealth_agent(state, mock_config)

        assert isinstance(result, Command)

    @pytest.mark.asyncio
    async def test_wealth_agent_worker_no_user_id(self, mocker):
        """Test wealth_agent worker handles missing user_id."""
        state = {"messages": [HumanMessage(content="Test")]}
        config = {"configurable": {}}

        result = await wealth_agent(state, config)

        assert isinstance(result, Command)
        assert "error" in str(result).lower() or "ERROR" in str(result)

    @pytest.mark.asyncio
    async def test_wealth_agent_worker_no_query(self, mock_config, mocker):
        """Test wealth_agent worker handles missing query."""
        state = {"messages": []}

        result = await wealth_agent(state, mock_config)

        assert isinstance(result, Command)
        assert "error" in str(result).lower() or "ERROR" in str(result)

    @pytest.mark.asyncio
    async def test_wealth_agent_worker_extracts_user_id_from_config(self, mock_config, mocker):
        """Test wealth_agent worker extracts user_id from config."""
        state = {"messages": [HumanMessage(content="Test query")]}

        mock_instance = MagicMock()
        mock_command = Command(
            update={"messages": [{"role": "assistant", "content": "Response"}]},
            goto="supervisor"
        )
        mock_instance.process_query_with_agent = AsyncMock(return_value=mock_command)

        mocker.patch("app.agents.supervisor.wealth_agent.agent.get_wealth_agent", return_value=mock_instance)

        await wealth_agent(state, mock_config)

        user_id_arg = mock_instance.process_query_with_agent.call_args[0][1]
        assert user_id_arg == mock_config["configurable"]["user_id"]

    @pytest.mark.asyncio
    async def test_wealth_agent_worker_extracts_query_from_messages(self, mock_config, mocker):
        """Test wealth_agent worker extracts query from messages."""
        test_query = "What is compound interest?"
        state = {"messages": [HumanMessage(content=test_query)]}

        mock_instance = MagicMock()
        mock_command = Command(
            update={"messages": [{"role": "assistant", "content": "Response"}]},
            goto="supervisor"
        )
        mock_instance.process_query_with_agent = AsyncMock(return_value=mock_command)

        mocker.patch("app.agents.supervisor.wealth_agent.agent.get_wealth_agent", return_value=mock_instance)

        await wealth_agent(state, mock_config)

        query_arg = mock_instance.process_query_with_agent.call_args[0][0]
        assert query_arg == test_query

    @pytest.mark.asyncio
    async def test_wealth_agent_worker_handles_exception(self, mock_config, mocker):
        """Test wealth_agent worker handles unexpected exceptions."""
        state = {"messages": [HumanMessage(content="Test")]}

        mocker.patch(
            "app.agents.supervisor.wealth_agent.agent.get_wealth_agent",
            side_effect=Exception("Unexpected error")
        )

        result = await wealth_agent(state, mock_config)

        assert isinstance(result, Command)
        assert result.goto == "supervisor"

    @pytest.mark.asyncio
    async def test_wealth_agent_worker_returns_command(self, mock_config, mocker):
        """Test wealth_agent worker always returns Command."""
        state = {"messages": [HumanMessage(content="Test")]}

        mock_instance = MagicMock()
        mock_command = Command(
            update={"messages": [{"role": "assistant", "content": "Response"}]},
            goto="supervisor"
        )
        mock_instance.process_query_with_agent = AsyncMock(return_value=mock_command)

        mocker.patch("app.agents.supervisor.wealth_agent.agent.get_wealth_agent", return_value=mock_instance)

        result = await wealth_agent(state, mock_config)

        assert isinstance(result, Command)
        assert hasattr(result, "update")
        assert hasattr(result, "goto")

    @pytest.mark.asyncio
    async def test_wealth_agent_worker_fallback_user_id_from_messages(self, mocker):
        """Test wealth_agent worker falls back to extracting user_id from messages."""
        user_id = uuid4()
        state = {
            "messages": [
                {"role": "user", "content": "Test", "user_id": str(user_id)}
            ]
        }
        config = {"configurable": {}}

        mock_instance = MagicMock()
        mock_command = Command(
            update={"messages": [{"role": "assistant", "content": "Response"}]},
            goto="supervisor"
        )
        mock_instance.process_query_with_agent = AsyncMock(return_value=mock_command)

        mocker.patch("app.agents.supervisor.wealth_agent.agent.get_wealth_agent", return_value=mock_instance)

        result = await wealth_agent(state, config)

        assert isinstance(result, Command)
