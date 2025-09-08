from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool
from langgraph.graph import MessagesState
from langgraph.prebuilt import InjectedState
from langgraph.types import Command, Send


def create_task_description_handoff_tool(*, agent_name: str, description: str | None = None) -> tool:

    name = f"transfer_to_{agent_name}"
    tool_description = description or f"Ask {agent_name} for help."

    @tool(name, description=tool_description)
    def handoff_tool(
        task_description: Annotated[
            str,
            "Description of what the next agent should do, including all of the relevant context.",
        ],
        state: Annotated[MessagesState, InjectedState],
    ) -> Command:
        # Extract user_id from configurable/session context (not messages)
        user_id = state.get("configurable", {}).get("user_id")

        # Create task description message with preserved user_id
        task_description_message = {
            "role": "user",
            "content": task_description,
            "user_id": user_id
        }

        agent_input = {**state, "messages": [task_description_message]}
        return Command(
            goto=[Send(agent_name, agent_input)],
            graph=Command.PARENT,
        )

    return handoff_tool


