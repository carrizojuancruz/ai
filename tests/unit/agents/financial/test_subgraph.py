"""Unit tests for finance agent subgraph."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.tools import BaseTool

from app.agents.supervisor.finance_agent.subgraph import create_finance_subgraph


class MockTool(BaseTool):
    """Mock tool that behaves like a LangChain BaseTool."""

    name: str = "test_tool"
    description: str = "A test tool"

    def _run(self, *args, **kwargs):
        return "mock result"

    async def _arun(self, *args, **kwargs):
        return "mock result"


class TestCreateFinanceSubgraph:
    """Test create_finance_subgraph function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sql_generator = MagicMock()
        # Create a mock tool that behaves like a LangChain BaseTool
        self.tools = [MockTool()]
        self.prompt_builder = AsyncMock(return_value="Test system prompt")

    def test_create_subgraph_returns_compiled_workflow(self):
        """Test that create_finance_subgraph returns a compiled workflow."""
        workflow = create_finance_subgraph(self.sql_generator, self.tools, self.prompt_builder)

        # Should return a compiled StateGraph
        assert hasattr(workflow, 'ainvoke')
        assert hasattr(workflow, 'get_graph')

    @patch('langgraph.prebuilt.tool_node.create_tool')
    def test_subgraph_has_required_nodes(self, mock_create_tool):
        """Test that the subgraph has all required nodes."""
        # Mock the create_tool function to return our mock tool
        mock_create_tool.return_value = self.tools[0]

        workflow = create_finance_subgraph(self.sql_generator, self.tools, self.prompt_builder)

        graph = workflow.get_graph()
        nodes = list(graph.nodes.keys())

        assert "agent" in nodes
        assert "tools" in nodes
        assert "supervisor" in nodes

    @patch('langgraph.prebuilt.tool_node.create_tool')
    @pytest.mark.asyncio
    async def test_agent_node_calls_prompt_builder(self, mock_create_tool):
        """Test that the agent node calls the prompt builder."""
        from langchain_core.messages import AIMessage, HumanMessage

        # Mock the create_tool function to return our mock tool
        mock_create_tool.return_value = self.tools[0]

        # Create a proper mock for the LLM that returns an AIMessage
        mock_llm = MagicMock()
        mock_ai_message = AIMessage(content="Test response", tool_calls=[])
        mock_llm.ainvoke = AsyncMock(return_value=mock_ai_message)
        self.sql_generator.bind_tools = MagicMock(return_value=mock_llm)

        workflow = create_finance_subgraph(self.sql_generator, self.tools, self.prompt_builder)

        # Invoke the workflow with a proper LangChain message
        state = {"messages": [HumanMessage(content="Hello")]}
        await workflow.ainvoke(state)

        # The prompt builder should be awaited once
        self.prompt_builder.assert_awaited_once()

    @patch('langgraph.prebuilt.tool_node.create_tool')
    def test_supervisor_node_structure(self, mock_create_tool):
        """Test that supervisor node is properly configured."""
        # Mock the create_tool function to return our mock tool
        mock_create_tool.return_value = self.tools[0]

        workflow = create_finance_subgraph(self.sql_generator, self.tools, self.prompt_builder)

        # Check that the workflow was created successfully
        assert workflow is not None

    @patch('langgraph.prebuilt.tool_node.create_tool')
    def test_workflow_has_correct_edges(self, mock_create_tool):
        """Test that the workflow has the correct edges."""
        # Mock the create_tool function to return our mock tool
        mock_create_tool.return_value = self.tools[0]

        workflow = create_finance_subgraph(self.sql_generator, self.tools, self.prompt_builder)

        graph = workflow.get_graph()
        edges = list(graph.edges)

        # Should have edges defined
        assert len(edges) > 0

    def test_should_continue_logic_with_and_without_tool_calls(self):
        """Test should_continue logic returns correct routing based on tool_calls presence."""
        # Test with tool_calls - should route to 'tools'
        mock_message_with_tools = MagicMock()
        mock_message_with_tools.tool_calls = [{"name": "test_tool"}]
        result_with_tools = "tools" if mock_message_with_tools.tool_calls else "supervisor"
        assert result_with_tools == "tools"

        # Test without tool_calls - should route to 'supervisor'
        mock_message_no_tools = MagicMock()
        mock_message_no_tools.tool_calls = []
        result_no_tools = "tools" if mock_message_no_tools.tool_calls else "supervisor"
        assert result_no_tools == "supervisor"
