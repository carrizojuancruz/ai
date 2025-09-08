from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, ToolCall, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import MessagesState
from langgraph.prebuilt import InjectedState
from langgraph.types import Command, Send


def create_task_description_handoff_tool(*, agent_name: str, description: str | None = None) -> tool:
    """Create a tool that delegates tasks to subagents using proper tool calls."""
    name = f"transfer_to_{agent_name}"
    tool_description = description or f"Delegate a task to the {agent_name} for specialized analysis."

    @tool(name, description=tool_description)
    def handoff_tool(
        task_description: Annotated[
            str,
            "Clear description of the task for the subagent to complete, including all relevant context and requirements.",
        ],
        state: Annotated[MessagesState, InjectedState],
    ) -> Command:
        """Delegate task to subagent using proper tool call mechanism."""
        # Create delegation message with proper context
        delegation_prompt = f"""
        Please analyze and complete the following task as a specialized agent.
        You are providing analysis to your supervisor - they will format the final response to the user.

        Task: {task_description}

        Instructions:
        - Focus on gathering and analyzing the requested data
        - Provide comprehensive analysis with insights
        - Return your findings clearly and completely
        - Your supervisor will handle the final user-facing response
        """

        task_message = HumanMessage(
            content=delegation_prompt,
            name="supervisor_delegator"
        )

        return Command(
            graph=Command.PARENT,
            goto=Send(agent_name, {"messages": [task_message]}),
        )

    return handoff_tool


def create_handoff_back_messages(agent_name: str, supervisor_name: str) -> tuple[AIMessage, ToolMessage]:
    """Create messages to signal completion and return control to supervisor."""
    tool_call_id = str(uuid4())
    tool_name = f"transfer_back_to_{supervisor_name}"

    tool_calls = [ToolCall(name=tool_name, args={}, id=tool_call_id)]

    return (
        AIMessage(
            content=f"Analysis completed. Returning control to {supervisor_name}.",
            tool_calls=tool_calls,
            name=agent_name,
            response_metadata={"is_handoff_back": True},
        ),
        ToolMessage(
            content=f"Successfully returned control to {supervisor_name}",
            name=tool_name,
            tool_call_id=tool_call_id,
            response_metadata={"is_handoff_back": True},
        ),
    )


