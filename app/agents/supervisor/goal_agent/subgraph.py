from typing import Callable, List

from langchain_aws import ChatBedrockConverse
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from .handoff import handoff_to_supervisor_node


class GoalSubgraph:
    """Class to create and manage the goal subgraph workflow."""

    # Constants
    DEFAULT_ANALYSIS_CONTENT = "Goal analysis completed successfully."
    RESPONSE_TEMPLATE = """===== GOAL AGENT TASK COMPLETED =====

Task Analyzed: {user_question}

Analysis Results:
{analysis_content}

STATUS: GOAL AGENT ANALYSIS COMPLETE
This goal agent analysis is provided to the supervisor for final user response formatting."""

    def __init__(self, llm: ChatBedrockConverse, tools: List[BaseTool], prompt_builder: Callable[[], str]):
        self.llm = llm
        self.tools = tools
        self.prompt_builder = prompt_builder

    def create(self):
        """Create the goal subgraph workflow."""
        tool_node = ToolNode(self.tools)
        model_with_tools = self.llm.bind_tools(self.tools)

        async def agent_node(state: MessagesState) -> dict:
            """Agent node that processes messages with tools."""
            system_prompt = self.prompt_builder()

            # Filter messages to only include valid roles for Bedrock
            valid_messages = []
            for msg in state["messages"]:
                if isinstance(msg, dict):
                    if msg.get("role") in ["user", "assistant"]:
                        valid_messages.append(msg)
                else:
                    # Assume it's a BaseMessage (HumanMessage, AIMessage, etc.)
                    valid_messages.append(msg)

            messages = [{"role": "system", "content": system_prompt}] + valid_messages
            response = await model_with_tools.ainvoke(messages)
            return {"messages": [response]}

        def supervisor_node(state: MessagesState) -> dict:
            """Supervisor node that formats the final response."""
            user_question = ""
            for msg in state["messages"]:
                if hasattr(msg, "content") and getattr(msg, "type", None) == "human":
                    user_question = str(msg.content)
                    break

            analysis_content = ""
            for msg in reversed(state["messages"]):
                if (msg.__class__.__name__ == "AIMessage" and
                    hasattr(msg, "content") and msg.content and
                    not getattr(msg, "tool_calls", None)):
                    if isinstance(msg.content, list):
                        text_parts = [item.get("text", "") for item in msg.content if isinstance(item, dict)]
                        analysis_content = "".join(text_parts)
                    else:
                        analysis_content = str(msg.content)
                    break

            if not analysis_content.strip():
                analysis_content = self.DEFAULT_ANALYSIS_CONTENT

            formatted_response = self.RESPONSE_TEMPLATE.format(
                user_question=user_question,
                analysis_content=analysis_content
            )

            return {
                "messages": [
                    {"role": "assistant", "content": formatted_response, "name": "goal_agent"}
                ]
            }

        def should_continue(state: MessagesState) -> str:
            """Determine if to continue with tools or supervisor."""
            last_message = state["messages"][-1]
            return "tools" if last_message.tool_calls else "supervisor"

        workflow = StateGraph(MessagesState)
        workflow.add_node("agent", agent_node)
        workflow.add_node("tools", tool_node)
        workflow.add_node("supervisor", supervisor_node)
        workflow.add_node("handoff_to_supervisor", handoff_to_supervisor_node)

        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges("agent", should_continue)
        workflow.add_edge("tools", "agent")
        workflow.add_edge("supervisor", "handoff_to_supervisor")
        workflow.add_edge("handoff_to_supervisor", END)

        return workflow.compile(checkpointer=None)


def create_goal_subgraph(llm: ChatBedrockConverse, tools: List[BaseTool], prompt_builder: Callable[[], str]):
    """Create the goal subgraph."""
    subgraph = GoalSubgraph(llm, tools, prompt_builder)
    return subgraph.create()
