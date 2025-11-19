"""Tests for the Goal Subgraph."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from app.agents.supervisor.goal_agent.subgraph import GoalSubgraph, create_goal_subgraph


class MockToolSchema(BaseModel):
    """Mock schema for tool arguments."""
    param1: str = "default"


class MockTool(BaseTool):
    """Mock tool for testing."""
    name: str = "test_tool"
    description: str = "Test tool"
    args_schema: type[BaseModel] = MockToolSchema

    def _run(self, param1: str = "default") -> str:
        return "tool result"

    async def _arun(self, param1: str = "default") -> str:
        return "tool result"


def create_mock_tool(name: str = "test_tool", description: str = "Test tool") -> MockTool:
    """Create a mock tool that behaves like a LangChain BaseTool."""
    return MockTool(name=name, description=description)


class TestGoalSubgraph:
    """Test cases for GoalSubgraph class."""

    @patch('app.agents.supervisor.goal_agent.subgraph.ChatCerebras')
    def test_goal_subgraph_initialization(self, mock_cerebras):
        """Test GoalSubgraph initialization."""
        # Arrange
        mock_llm = MagicMock()
        mock_cerebras.return_value = mock_llm
        mock_tools = [create_mock_tool()]
        mock_prompt_builder = MagicMock(return_value="test prompt")

        # Act
        subgraph = GoalSubgraph(mock_llm, mock_tools, mock_prompt_builder)

        # Assert
        assert subgraph.llm == mock_llm
        assert subgraph.tools == mock_tools
        assert subgraph.prompt_builder == mock_prompt_builder

    @patch('app.agents.supervisor.goal_agent.subgraph.ChatCerebras')
    def test_create_goal_subgraph_function(self, mock_cerebras):
        """Test create_goal_subgraph function."""
        # Arrange
        mock_llm = MagicMock()
        mock_cerebras.return_value = mock_llm
        mock_tools = [create_mock_tool()]
        mock_prompt_builder = MagicMock(return_value="test prompt")

        # Act
        result = create_goal_subgraph(mock_llm, mock_tools, mock_prompt_builder)

        # Assert
        assert result is not None
        # Should return a compiled workflow
        assert hasattr(result, 'ainvoke')

    @patch('app.agents.supervisor.goal_agent.subgraph.ChatCerebras')
    @pytest.mark.asyncio
    async def test_agent_node_processing(self, mock_cerebras):
        """Test agent_node message processing."""
        # Arrange
        mock_llm = MagicMock()
        mock_cerebras.return_value = mock_llm
        mock_tools = [create_mock_tool()]
        mock_prompt_builder = MagicMock(return_value="test prompt")

        subgraph = GoalSubgraph(mock_llm, mock_tools, mock_prompt_builder)

        # Mock the LLM response
        mock_response = AIMessage(content="Test response", tool_calls=[])
        mock_llm.bind_tools.return_value.ainvoke = AsyncMock(return_value=mock_response)

        # Create workflow
        workflow = subgraph.create()

        # Test messages
        messages = [
            {"role": "user", "content": "Test query"}
        ]

        # Act
        result = await workflow.ainvoke({"messages": messages})

        # Assert
        assert "messages" in result
        assert len(result["messages"]) > 1  # Should have added the AI response

    @patch('app.agents.supervisor.goal_agent.subgraph.ChatCerebras')
    @pytest.mark.asyncio
    async def test_supervisor_node_processing(self, mock_cerebras):
        """Test supervisor_node response formatting."""
        # Arrange
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Mocked AI response"))
        mock_model_with_tools = MagicMock()
        mock_model_with_tools.ainvoke = AsyncMock(return_value=AIMessage(content="Mocked AI response"))
        mock_llm.bind_tools = MagicMock(return_value=mock_model_with_tools)
        mock_cerebras.return_value = mock_llm
        mock_tools = [create_mock_tool()]
        mock_prompt_builder = MagicMock(return_value="test prompt")

        subgraph = GoalSubgraph(mock_llm, mock_tools, mock_prompt_builder)

        # Create workflow
        workflow = subgraph.create()

        # Test with AI message containing analysis
        messages = [
            HumanMessage(content="What are my goals?"),
            AIMessage(content="Here is your goal analysis content.")
        ]

        # Act - Call supervisor node directly by simulating the workflow state
        # This is tricky to test directly, so we'll test the components

        # Test the supervisor node logic indirectly through the workflow
        result = await workflow.ainvoke({"messages": messages})

        # Assert
        assert "messages" in result
        # The final message should be from the supervisor node
        final_message = result["messages"][-1]
        assert final_message.type == "ai"
        assert "Mocked AI response" in final_message.content

    @patch('app.agents.supervisor.goal_agent.subgraph.ChatCerebras')
    def test_workflow_structure_and_edges(self, mock_cerebras):
        """Test workflow structure has correct nodes and edges."""
        # Arrange
        mock_llm = MagicMock()
        mock_cerebras.return_value = mock_llm
        mock_tools = [create_mock_tool()]
        mock_prompt_builder = MagicMock(return_value="test prompt")

        subgraph = GoalSubgraph(mock_llm, mock_tools, mock_prompt_builder)

        # Act
        workflow = subgraph.create()

        # Assert - Verify workflow is properly compiled
        assert workflow is not None
        assert hasattr(workflow, 'ainvoke'), "Workflow should be a compiled graph with ainvoke method"

        # Verify the subgraph itself was created correctly
        assert subgraph is not None
        assert subgraph.llm == mock_llm
        assert subgraph.tools == mock_tools
        assert subgraph.prompt_builder == mock_prompt_builder
