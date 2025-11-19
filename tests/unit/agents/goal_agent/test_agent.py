"""Tests for the Goal Agent."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.supervisor.goal_agent.agent import GoalAgent, compile_goal_agent_graph, get_goal_agent


class TestGoalAgent:
    """Test cases for GoalAgent class."""

    @patch('app.agents.supervisor.goal_agent.agent.ChatCerebras')
    @patch('app.agents.supervisor.goal_agent.agent.configure_logging')
    def test_goal_agent_initialization(self, mock_configure_logging, mock_cerebras):
        """Test GoalAgent initialization."""
        # Arrange
        mock_llm = MagicMock()
        mock_cerebras.return_value = mock_llm

        # Act
        agent = GoalAgent()

        # Assert
        assert agent.llm == mock_llm
        mock_cerebras.assert_called_once()
        mock_configure_logging.assert_called_once()

    @patch('app.agents.supervisor.goal_agent.agent.ChatCerebras')
    @patch('app.agents.supervisor.goal_agent.agent.configure_logging')
    def test_create_agent_with_tools(self, mock_configure_logging, mock_cerebras):
        """Test _create_agent_with_tools method."""
        # Arrange
        mock_llm = MagicMock()
        mock_cerebras.return_value = mock_llm
        agent = GoalAgent()

        with patch('app.agents.supervisor.goal_agent.agent.create_goal_subgraph') as mock_create_subgraph:
            mock_workflow = MagicMock()
            mock_create_subgraph.return_value = mock_workflow

            # Act
            result = agent._create_agent_with_tools()

            # Assert
            assert result == mock_workflow
            mock_create_subgraph.assert_called_once()
            args, kwargs = mock_create_subgraph.call_args
            assert args[0] == mock_llm
            assert len(args[1]) == 8  # Should have 8 tools
            assert callable(args[2])  # prompt_builder should be callable

    @patch('app.agents.supervisor.goal_agent.agent.ChatCerebras')
    @patch('app.agents.supervisor.goal_agent.agent.configure_logging')
    def test_create_system_prompt(self, mock_configure_logging, mock_cerebras):
        """Test _create_system_prompt method."""
        # Arrange
        mock_llm = MagicMock()
        mock_cerebras.return_value = mock_llm
        agent = GoalAgent()

        # Act
        prompt = agent._create_system_prompt()

        # Assert
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "GOAL AGENT" in prompt

    @patch('app.agents.supervisor.goal_agent.agent.ChatCerebras')
    @patch('app.agents.supervisor.goal_agent.agent.configure_logging')
    @pytest.mark.asyncio
    async def test_process_query_with_agent(self, mock_configure_logging, mock_cerebras):
        """Test process_query_with_agent method."""
        # Arrange
        mock_llm = MagicMock()
        mock_cerebras.return_value = mock_llm
        agent = GoalAgent()

        mock_workflow = AsyncMock()
        mock_command = MagicMock()
        mock_workflow.ainvoke.return_value = mock_command

        with patch.object(agent, '_create_agent_with_tools', return_value=mock_workflow):
            result = await agent.process_query_with_agent("Test query", "user123")

            assert result == mock_command
            mock_workflow.ainvoke.assert_called_once_with(
                {"messages": [{"role": "user", "content": "Test query"}]},
                config={
                    "recursion_limit": 10,
                    "callbacks": [],
                    "configurable": {"user_id": "user123"}
                }
            )


class TestGoalAgentGlobalFunctions:
    """Test cases for global functions."""

    @patch('app.agents.supervisor.goal_agent.agent.GoalAgent')
    def test_compile_goal_agent_graph(self, mock_goal_agent_class):
        """Test compile_goal_agent_graph function."""
        # Arrange
        mock_agent = MagicMock()
        mock_workflow = MagicMock()
        mock_agent._create_agent_with_tools.return_value = mock_workflow
        mock_goal_agent_class.return_value = mock_agent

        # Act
        result = compile_goal_agent_graph()

        # Assert
        assert result == mock_workflow
        mock_goal_agent_class.assert_called_once()
        mock_agent._create_agent_with_tools.assert_called_once()

    @patch('app.agents.supervisor.goal_agent.agent.GoalAgent')
    def test_get_goal_agent_singleton(self, mock_goal_agent_class):
        """Test get_goal_agent singleton pattern."""
        # Arrange
        mock_agent1 = MagicMock()
        mock_agent2 = MagicMock()
        mock_goal_agent_class.side_effect = [mock_agent1, mock_agent2]

        # Act
        result1 = get_goal_agent()
        result2 = get_goal_agent()

        # Assert
        assert result1 == mock_agent1
        assert result2 == mock_agent1  # Should return the same instance
        mock_goal_agent_class.assert_called_once()  # Only called once due to singleton
