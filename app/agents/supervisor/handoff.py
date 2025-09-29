from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import MessagesState
from langgraph.prebuilt import InjectedState
from langgraph.types import Command, Send


def create_task_description_handoff_tool(
    *,
    agent_name: str,
    description: str | None = None,
    destination_agent_name: str | None = None,
    tool_name: str | None = None,
    guidelines: str | None = None,
) -> tool:
    """Create a tool that delegates tasks to subagents using proper tool call mechanics.

    agent_name controls the semantic name used in descriptions. The tool's actual
    registered name can be overridden via tool_name. The graph destination can be
    overridden via destination_agent_name (defaults to agent_name).
    """
    name = tool_name or f"transfer_to_{agent_name}"
    dest = destination_agent_name or agent_name
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

        instruction_block = ""
        if guidelines is not None:
            instruction_block = "\n".join([f"- {line}" for line in guidelines.split("\n")])

        delegation_prompt = f"""
        Please analyze and complete the following task as a specialized agent.
        You are providing analysis to your supervisor - they will format the final response to the user.

        Task: {task_description}

        Guidelines:
        {instruction_block}
        """

        task_message = HumanMessage(
            content=delegation_prompt,
            name="supervisor_delegator"
        )

        return Command(graph=Command.PARENT, goto=Send(dest, {"messages": [task_message]}))

    return handoff_tool


def create_handoff_back_messages(agent_name: str, supervisor_name: str) -> tuple[AIMessage, ToolMessage]:
    """Create messages to signal completion and return control to supervisor."""
    tool_call_id = str(uuid4())
    tool_name = f"transfer_back_to_{supervisor_name}"

    return (
        AIMessage(
            content=f"Analysis completed. Returning control to {supervisor_name}.",
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


