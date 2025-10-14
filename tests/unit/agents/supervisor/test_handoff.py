import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.graph import MessagesState
from langgraph.types import Command, Send

from app.agents.supervisor.handoff import (
    create_handoff_back_messages,
    create_task_description_handoff_tool,
)


@pytest.mark.unit
class TestCreateTaskDescriptionHandoffTool:

    def test_create_handoff_tool_basic(self):
        tool = create_task_description_handoff_tool(
            agent_name="test_agent",
            description="Test agent description",
        )

        assert tool is not None
        assert callable(tool)
        assert tool.name == "transfer_to_test_agent"

    def test_create_handoff_tool_with_custom_tool_name(self):
        tool = create_task_description_handoff_tool(
            agent_name="test_agent",
            tool_name="custom_transfer_tool",
        )

        assert tool.name == "custom_transfer_tool"

    def test_create_handoff_tool_with_destination_agent_name(self):
        tool = create_task_description_handoff_tool(
            agent_name="display_name",
            destination_agent_name="actual_destination",
        )

        # The destination is used internally, not exposed in tool metadata
        assert tool.name == "transfer_to_display_name"

    def test_create_handoff_tool_has_description(self):
        description = "Specialized agent for financial analysis"
        tool = create_task_description_handoff_tool(
            agent_name="finance_agent",
            description=description,
        )

        assert tool.description == description

    def test_create_handoff_tool_default_description(self):
        tool = create_task_description_handoff_tool(agent_name="test_agent")

        assert "test_agent" in tool.description
        assert "specialized analysis" in tool.description.lower()

    def test_create_handoff_tool_with_guidelines(self):
        guidelines = "Follow these rules\nBe concise\nValidate input"
        tool = create_task_description_handoff_tool(
            agent_name="test_agent",
            guidelines=guidelines,
        )

        assert tool is not None
        assert callable(tool)

    def test_handoff_tool_invocation_returns_command(self):
        tool = create_task_description_handoff_tool(
            agent_name="test_agent",
        )

        state = MessagesState(messages=[])
        result = tool.invoke(
            {
                "task_description": "Analyze user spending",
                "state": state,
            }
        )

        assert isinstance(result, Command)

    def test_handoff_tool_command_has_correct_graph(self):
        tool = create_task_description_handoff_tool(
            agent_name="test_agent",
        )

        state = MessagesState(messages=[])
        result = tool.invoke(
            {
                "task_description": "Test task",
                "state": state,
            }
        )

        assert result.graph == Command.PARENT

    def test_handoff_tool_command_includes_task_description(self):
        tool = create_task_description_handoff_tool(
            agent_name="test_agent",
        )

        task = "Analyze quarterly expenses"
        state = MessagesState(messages=[])
        result = tool.invoke(
            {
                "task_description": task,
                "state": state,
            }
        )

        # Check that goto contains Send with task in messages
        assert isinstance(result.goto, Send)
        assert "messages" in result.goto.arg
        messages = result.goto.arg["messages"]
        assert len(messages) > 0
        assert task in str(messages[0].content)

    def test_handoff_tool_with_guidelines_includes_them_in_message(self):
        guidelines = "Be precise\nUse SQL\nReturn summary"
        tool = create_task_description_handoff_tool(
            agent_name="test_agent",
            guidelines=guidelines,
        )

        state = MessagesState(messages=[])
        result = tool.invoke(
            {
                "task_description": "Test task",
                "state": state,
            }
        )

        # Guidelines should be in the message content
        messages = result.goto.arg["messages"]
        content = str(messages[0].content)
        assert "Be precise" in content or "Guidelines" in content

    def test_handoff_tool_send_targets_correct_destination(self):
        tool = create_task_description_handoff_tool(
            agent_name="finance_agent",
            destination_agent_name="finance_router",
        )

        state = MessagesState(messages=[])
        result = tool.invoke(
            {
                "task_description": "Test",
                "state": state,
            }
        )

        # Should send to finance_router, not finance_agent
        assert isinstance(result.goto, Send)
        assert result.goto.node == "finance_router"

    def test_handoff_tool_send_targets_agent_name_when_no_destination(self):
        tool = create_task_description_handoff_tool(
            agent_name="goal_agent",
        )

        state = MessagesState(messages=[])
        result = tool.invoke(
            {
                "task_description": "Test",
                "state": state,
            }
        )

        assert isinstance(result.goto, Send)
        assert result.goto.node == "goal_agent"

    def test_handoff_tool_creates_human_message(self):
        tool = create_task_description_handoff_tool(
            agent_name="test_agent",
        )

        state = MessagesState(messages=[])
        result = tool.invoke(
            {
                "task_description": "Analyze data",
                "state": state,
            }
        )

        messages = result.goto.arg["messages"]
        assert len(messages) == 1
        # Should be a HumanMessage
        assert hasattr(messages[0], "content")
        assert messages[0].name == "supervisor_delegator"


@pytest.mark.unit
class TestCreateHandoffBackMessages:

    def test_creates_valid_message_tuple(self):
        """Test that function returns a tuple of two messages with correct types."""
        result = create_handoff_back_messages(
            agent_name="test_agent",
            supervisor_name="supervisor",
        )

        assert isinstance(result, tuple)
        assert len(result) == 2

        ai_msg, tool_msg = result
        assert ai_msg is not None
        assert tool_msg is not None
        assert isinstance(ai_msg, AIMessage)
        assert isinstance(tool_msg, ToolMessage)

    def test_ai_message_properties(self):
        """Test AI message has correct content, name, and metadata."""
        agent_name = "wealth_agent"
        supervisor_name = "custom_supervisor"

        ai_msg, _ = create_handoff_back_messages(
            agent_name=agent_name,
            supervisor_name=supervisor_name,
        )

        # Check content
        assert "completed" in ai_msg.content.lower()
        assert supervisor_name in ai_msg.content

        # Check name
        assert ai_msg.name == agent_name

        # Check handoff metadata
        assert hasattr(ai_msg, "response_metadata")
        assert ai_msg.response_metadata.get("is_handoff_back") is True

    def test_tool_message_properties(self):
        """Test tool message has correct content, name, metadata, and unique ID."""
        supervisor_name = "supervisor"

        _, tool_msg = create_handoff_back_messages(
            agent_name="test_agent",
            supervisor_name=supervisor_name,
        )

        # Check content
        assert "Successfully returned control" in tool_msg.content
        assert supervisor_name in tool_msg.content

        # Check name includes supervisor_name
        assert tool_msg.name == f"transfer_back_to_{supervisor_name}"

        # Check tool_call_id exists
        assert hasattr(tool_msg, "tool_call_id")
        assert tool_msg.tool_call_id is not None
        assert len(tool_msg.tool_call_id) > 0

        # Check handoff metadata
        assert hasattr(tool_msg, "response_metadata")
        assert tool_msg.response_metadata.get("is_handoff_back") is True

    def test_tool_call_id_is_unique(self):
        """Test that tool_call_id is unique across different calls."""
        _, tool_msg1 = create_handoff_back_messages("agent1", "supervisor")
        _, tool_msg2 = create_handoff_back_messages("agent2", "supervisor")

        assert tool_msg1.tool_call_id != tool_msg2.tool_call_id
