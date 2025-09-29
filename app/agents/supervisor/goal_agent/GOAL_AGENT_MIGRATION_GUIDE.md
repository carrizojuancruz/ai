# Goal Agent Migration Guide

## Current State Analysis

The Goal Agent currently uses an **outdated architecture** compared to the modern Wealth Agent patterns. This document provides a comprehensive migration plan to align the Goal Agent with the current best practices.

## Table of Contents

1. [Current Architecture Problems](#current-architecture-problems)
2. [Target Architecture](#target-architecture)
3. [Migration Strategy](#migration-strategy)
4. [Detailed Implementation Plan](#detailed-implementation-plan)
5. [Migration Checklist](#migration-checklist)
6. [Testing Strategy](#testing-strategy)
7. [Rollback Plan](#rollback-plan)

## Current Architecture Problems

### 1. **Outdated LangGraph Pattern**
```python
# Current (OLD): Simple create_react_agent
goal_agent = create_react_agent(
    model=chat_bedrock,
    tools=[create_goal, update_goal, ...],
    prompt=GOAL_AGENT_PROMPT,
    name="goal_agent",
)
```

**Problems**:
- ❌ No response cleaning for OpenAI model quirks
- ❌ No tool call limiting
- ❌ No reasoning content filtering
- ❌ Uses outdated create_react_agent pattern

### 2. **Singleton Pattern Issues**
```python
# Current: Singleton with threading locks
class GoalAgentSingleton:
    _instance: Optional['GoalAgentSingleton'] = None
    _lock = threading.Lock()
```

**Problems**:
- ❌ Shared state across different supervisor tasks
- ❌ Conversation state pollution between users
- ❌ Complex singleton management

### 3. **Missing State Isolation**
```python
# Current: Uses shared thread_id
goal_config = {
    "configurable": {
        "thread_id": thread_id,  # ❌ Shared across tasks
        "user_id": user_id
    }
}
```

**Problems**:
- ❌ Conversation history bleeds between supervisor tasks
- ❌ Tool call counts accumulate incorrectly
- ❌ State pollution issues

### 4. **No Response Quality Control**
**Problems**:
- ❌ No handling of reasoning content exposure
- ❌ No tool call limit enforcement
- ❌ No response cleaning for model quirks

## Target Architecture

### 1. **Modern Subgraph Pattern** (Like Wealth Agent)
```
START → agent_node → {tools|supervisor} → handoff_to_supervisor → END
          ↑              ↓
          └── tool_node ←─┘
```

### 2. **Fresh Graph Creation** (No Singleton)
```python
def get_goal_agent_graph():
    """Get fresh goal agent graph for each supervisor task."""
    return compile_goal_agent_graph()  # Fresh instance
```

### 3. **Unique Thread IDs**
```python
unique_thread_id = f"goal-task-{uuid.uuid4()}"
```

### 4. **Response Cleaning System**
```python
def _clean_response(response, tool_call_count: int, state: dict, logger):
    # Handle tool call limits, reasoning content, etc.
```

## Migration Strategy

### Phase 1: Create New Architecture (Parallel)
- Create new goal_agent directory structure
- Implement modern subgraph pattern
- Keep existing singleton as fallback

### Phase 2: Update Integration Points
- Update workers.py integration
- Modify supervisor registration
- Add state isolation

### Phase 3: Testing & Validation
- Run parallel testing
- Validate functionality
- Performance testing

### Phase 4: Switch & Cleanup
- Switch to new architecture
- Remove old singleton code
- Clean up imports

## Detailed Implementation Plan

### Step 1: Create New Directory Structure

```
goal_agent/
├── agent.py           # NEW: GoalAgent class (like WealthAgent)
├── subgraph.py        # NEW: Modern LangGraph subgraph
├── prompts.py         # MIGRATE: Existing prompts with enhancements
├── tools.py           # KEEP: Existing CRUD tools (already good)
├── handoff.py         # KEEP: Existing handoff logic
├── helpers.py         # NEW: Response cleaning utilities
├── models.py          # KEEP: Existing Pydantic models
└── utils.py           # KEEP: Existing API utilities
```

### Step 2: Implement GoalAgent Class

**Create `goal_agent/agent.py`**:

```python
from __future__ import annotations

import logging
from typing import Callable
from uuid import UUID

from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from app.core.config import config
from app.observability.logging_config import configure_logging

from .helpers import create_error_command
from .prompts import build_goal_system_prompt
from .tools import (
    create_goal, update_goal, get_in_progress_goal,
    list_goals, delete_goal, switch_goal_status, get_goal_by_id
)

logger = logging.getLogger(__name__)


class GoalAgent:
    """Goal agent for financial objectives management and coaching."""

    def __init__(self):
        configure_logging()
        
        logger.info("Initializing GoalAgent with Bedrock models")
        
        self.llm = ChatBedrockConverse(
            model_id=config.GOAL_AGENT_MODEL_ID,
            region_name=config.GOAL_AGENT_MODEL_REGION,
            temperature=config.GOAL_AGENT_TEMPERATURE,
        )
        
        logger.info("GoalAgent initialization completed")

    def _create_system_prompt(self, user_context: dict = None) -> str:
        """Create system prompt for the goal agent."""
        return build_goal_system_prompt(user_context)

    def _create_agent_with_tools(self):
        """Create goal agent with CRUD tools."""
        from .subgraph import create_goal_subgraph
        
        logger.info("Creating goal agent with CRUD tools")
        
        tools = [
            create_goal, update_goal, get_in_progress_goal,
            list_goals, delete_goal, switch_goal_status, get_goal_by_id
        ]
        
        prompt_builder = lambda: self._create_system_prompt()
        
        return create_goal_subgraph(self.llm, tools, prompt_builder)

    async def process_query_with_agent(self, query: str, user_id: UUID) -> Command:
        """Process goal queries and return Command from agent execution."""
        try:
            logger.info(f"Processing goal query with agent for user {user_id}: {query}")
            
            # For supervisor handoffs, always create a fresh agent to avoid
            # carrying over conversation state and tool call counts from previous tasks
            agent = self._create_agent_with_tools()
            logger.info("Created fresh LangGraph agent for supervisor task")
                
            messages = [HumanMessage(content=query)]
            
            logger.info(f"Starting LangGraph agent execution for user {user_id}")
            agent_command = await agent.ainvoke({"messages": messages}, config={"recursion_limit": 10})
            logger.info(f"Agent execution completed for user {user_id}")
            
            return agent_command
            
        except Exception as e:
            logger.error(f"Goal agent error for user {user_id}: {e}")
            return create_error_command("I encountered an error while processing your goal request. Please try again.")


def compile_goal_agent_graph() -> CompiledStateGraph:
    """Compile the goal agent graph."""
    configure_logging()

    # Use new GoalAgent class directly
    goal_agent_instance = GoalAgent()
    return goal_agent_instance._create_agent_with_tools()


async def goal_agent(state, config):
    """Goal agent worker function that returns Command like finance agent."""
    try:
        from app.agents.supervisor.handoff import create_handoff_back_messages
        from app.utils.tools import get_config_value

        from .helpers import (
            create_error_command,
            get_last_user_message_text,
            get_user_id_from_messages,
        )

        user_id = get_config_value(config, "user_id")
        if not user_id:
            user_id = get_user_id_from_messages(state["messages"])

        query = get_last_user_message_text(state["messages"])

        if not user_id:
            logger.warning("No user_id found in goal agent request")
            return create_error_command("ERROR: Cannot access goal data without user identification.")

        if not query:
            logger.warning("No task description found in goal agent request")
            return create_error_command("ERROR: No task description provided for analysis.")

        from app.core.app_state import get_goal_agent

        goal_agent_instance = get_goal_agent()
        agent_command = await goal_agent_instance.process_query_with_agent(query, user_id)

        return agent_command

    except Exception as e:
        logger.error(f"Goal agent critical error: {e}")

        from app.agents.supervisor.handoff import create_handoff_back_messages

        error_analysis = f"I'm sorry, I had a problem processing your goal request: {str(e)}"
        handoff_messages = create_handoff_back_messages("goal_agent", "supervisor")

        return Command(
            update={
                "messages": [
                    {"role": "assistant", "content": error_analysis, "name": "goal_agent"},
                    handoff_messages[0],
                ]
            },
            goto="supervisor",
        )
```

### Step 3: Implement Modern Subgraph

**Create `goal_agent/subgraph.py`**:

```python
from __future__ import annotations

from typing import Callable

from langchain_aws import ChatBedrockConverse
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from .handoff import handoff_to_supervisor_node


def _clean_response(response, tool_call_count: int, state: dict, logger):
    """Clean response from OpenAI model to handle its quirks."""
    # If response has tool calls, handle tool call limits and content cleaning
    if hasattr(response, "tool_calls") and response.tool_calls:
        current_calls = len(response.tool_calls)
        total_calls = tool_call_count + current_calls
        
        # Only block if tool call limit exceeded
        if total_calls > 5:
            logger.error(f"BLOCKED: Would exceed limit - {current_calls} new calls + {tool_call_count} existing = {total_calls}")
            # If we already have some tool calls, allow a response with the data we have
            if tool_call_count > 0:
                return {"role": "assistant", "content": "Based on my goal analysis, I have gathered sufficient information to provide a comprehensive response.", "name": "goal_agent"}
            # If no tool calls yet, limit to 5 calls
            else:
                # Truncate to 5 tool calls
                limited_tool_calls = response.tool_calls[:5]
                clean_response = {
                    "role": "assistant",
                    "name": "goal_agent",
                    "tool_calls": limited_tool_calls
                }
                logger.warning(f"Truncated tool calls from {current_calls} to {len(limited_tool_calls)}")
                return clean_response
        
        # For tool calls, clean the content but keep the tool calls
        if hasattr(response, "content") and isinstance(response.content, list):
            # Remove reasoning content blocks, keep text and tool calls
            cleaned_content = []
            for block in response.content:
                if isinstance(block, dict) and block.get("type") == "reasoning_content":
                    logger.info("Removed reasoning content from tool call response")
                    continue  # Skip reasoning content
                else:
                    cleaned_content.append(block)
            
            # Create clean response with filtered content
            clean_response = {
                "role": "assistant",
                "name": "goal_agent",
                "tool_calls": response.tool_calls
            }
            if cleaned_content:
                clean_response["content"] = cleaned_content
            return clean_response

        return response

    # For responses without tool calls, check if we should allow final response
    if hasattr(response, "content") and isinstance(response.content, list):
        has_reasoning = any(
            isinstance(block, dict) and block.get("type") == "reasoning_content"
            for block in response.content
        )
        if has_reasoning:
            # Check if there are any tool messages in the conversation (indicating tools were used)
            has_tool_results = any(
                msg.__class__.__name__ == "ToolMessage"
                for msg in state.get("messages", [])
            )
            
            # If no tools have been executed yet, block reasoning content (agent should use tools first)
            if not has_tool_results:
                logger.error("BLOCKED: Response with reasoning content but no tool results - agent should use tools first")
                return {"role": "assistant", "content": "I need to check your current goals to provide accurate guidance about this request.", "name": "goal_agent"}
            else:
                # If tools have been used, allow reasoning content in final response but clean it
                logger.info("Cleaning reasoning content from final response after tool usage")
                cleaned_content = []
                for block in response.content:
                    if isinstance(block, dict) and block.get("type") == "reasoning_content":
                        continue  # Skip reasoning content
                    else:
                        cleaned_content.append(block)
                
                if cleaned_content:
                    return {"role": "assistant", "content": cleaned_content, "name": "goal_agent"}
                else:
                    return {"role": "assistant", "content": "Based on my goal analysis, I was unable to find specific information about this request.", "name": "goal_agent"}

    return response


def _get_content_length(content) -> int:
    """Get meaningful content length from response."""
    if isinstance(content, str):
        return len(content.strip())
    elif isinstance(content, list):
        text_blocks = [
            block.get("text", "") for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return sum(len(text.strip()) for text in text_blocks)
    return 0


def create_goal_subgraph(
    llm: ChatBedrockConverse,
    tools,
    prompt_builder: Callable[[], str],
):
    """Create goal agent subgraph with multi-node architecture."""
    import logging
    logger = logging.getLogger(__name__)
    
    tool_node = ToolNode(tools)
    model_with_tools = llm.bind_tools(tools)

    async def agent_node(state: MessagesState):
        """Process messages with dynamic system prompt and goal tools."""
        # Count existing tool calls from assistant messages only (not tool results)
        tool_call_count = 0
        for msg in state["messages"]:
            if (hasattr(msg, "tool_calls") and msg.tool_calls and
                getattr(msg, "role", None) == "assistant"):
                tool_call_count += len(msg.tool_calls)
        
        # Hard limit: Stop after 5 tool calls
        if tool_call_count >= 5:
            logger.warning(f"Tool call limit reached ({tool_call_count}). Forcing completion.")
            return {"messages": [{"role": "assistant", "content": "Based on my goal analysis, I have gathered sufficient information to provide a comprehensive response.", "name": "goal_agent"}]}
        
        system_prompt = prompt_builder()
        messages = [{"role": "system", "content": system_prompt}] + state["messages"]

        logger.info(f"Agent processing with {tool_call_count} previous tool calls")
        response = await model_with_tools.ainvoke(messages)

        cleaned_response = _clean_response(response, tool_call_count, state, logger)
        return {"messages": [cleaned_response]}

    def supervisor_node(state: MessagesState):
        """Format analysis results and hand back to supervisor."""
        analysis_content = ""
        user_question = ""

        for msg in state["messages"]:
            if hasattr(msg, "content") and getattr(msg, "type", None) == "human":
                user_question = str(msg.content)
                break

        for msg in reversed(state["messages"]):
            if (msg.__class__.__name__ == "AIMessage" and
                hasattr(msg, "content") and msg.content and
                not getattr(msg, "tool_calls", None) and
                not getattr(msg, "response_metadata", {}).get("is_handoff_back", False)):

                content = msg.content

                if isinstance(content, list):
                    text_blocks = []
                    for content_block in content:
                        if (isinstance(content_block, dict) and
                            content_block.get("type") == "text" and
                            content_block.get("text")):
                            text_blocks.append(content_block["text"])

                    if text_blocks:
                        analysis_content = "\n\n".join(text_blocks)
                        break
                elif isinstance(content, str) and content.strip():
                    analysis_content = content
                    break

        if not analysis_content.strip():
            analysis_content = "The goal analysis did not return specific information for this request."

        formatted_response = f"""===== GOAL AGENT TASK COMPLETED =====

Task Analyzed: {user_question}

Analysis Results:
{analysis_content}

STATUS: GOAL AGENT ANALYSIS COMPLETE
This goal agent analysis is provided to the supervisor for final user response formatting."""

        return {
            "messages": [
                {"role": "assistant", "content": formatted_response, "name": "goal_agent"}
            ]
        }

    def should_continue(state: MessagesState):
        """Route based on tool calls vs completion."""
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return "tools"
        return "supervisor"

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
```

### Step 4: Create Helper Functions

**Create `goal_agent/helpers.py`**:

```python
from __future__ import annotations

from typing import Any
from uuid import UUID

from langgraph.types import Command


def create_error_command(error_message: str) -> Command:
    """Create error command with handoff back to supervisor."""
    from app.agents.supervisor.handoff import create_handoff_back_messages
    
    handoff_messages = create_handoff_back_messages("goal_agent", "supervisor")
    return Command(
        update={
            "messages": [
                {"role": "assistant", "content": error_message, "name": "goal_agent"},
                handoff_messages[0],
            ]
        },
        goto="supervisor",
    )


def get_last_user_message_text(messages: list[Any]) -> str:
    """Extract the last user message text from messages."""
    for msg in reversed(messages):
        if hasattr(msg, "content") and hasattr(msg, "type") and msg.type == "human":
            return str(msg.content)
    return ""


def get_user_id_from_messages(messages: list[Any]) -> UUID | None:
    """Extract user_id from messages if available."""
    # This is a fallback - normally user_id should come from config
    # Could potentially extract from message metadata if needed
    return None


def format_goal_response(goal_data: dict) -> str:
    """Format goal data for user-friendly display."""
    if not goal_data:
        return "No goal information available."
    
    # Format goal information in a user-friendly way
    goal_info = []
    
    if "goal" in goal_data:
        goal = goal_data["goal"]
        if isinstance(goal, dict):
            if "title" in goal:
                goal_info.append(f"**Goal**: {goal['title']}")
            if "description" in goal:
                goal_info.append(f"**Description**: {goal['description']}")
    
    if "status" in goal_data:
        goal_info.append(f"**Status**: {goal_data['status']}")
    
    if "amount" in goal_data:
        amount = goal_data["amount"]
        if isinstance(amount, dict) and "absolute" in amount:
            abs_amount = amount["absolute"]
            if "target" in abs_amount and "currency" in abs_amount:
                goal_info.append(f"**Target**: {abs_amount['currency']} {abs_amount['target']:,.2f}")
    
    return "\n".join(goal_info) if goal_info else "Goal information available but not formatted."


def validate_goal_data(goal_data: dict) -> tuple[bool, str]:
    """Validate goal data structure and return validation result."""
    if not isinstance(goal_data, dict):
        return False, "Goal data must be a dictionary"
    
    required_fields = ["goal", "category", "nature", "frequency", "amount"]
    missing_fields = [field for field in required_fields if field not in goal_data]
    
    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"
    
    return True, "Valid goal data"
```

### Step 5: Update System Prompts

**Enhance `goal_agent/prompts.py`**:

```python
from datetime import datetime

today = datetime.now().strftime("%B %d, %Y")

def build_goal_system_prompt(user_context: dict = None) -> str:
    """Build dynamic system prompt for goal agent."""
    base_prompt = f"""
TODAY: {today}

# GOAL AGENT SYSTEM PROMPT

## ROLE & PURPOSE
You are the Goal subagent for Verde AI's financial goals system. You help users define, track, and achieve
financial objectives through intelligent coaching and CRUD operations. You are providing analysis to your 
supervisor - they will format the final response to the user.

**Language**: English
**Role**: Specialized financial goals assistant with full CRUD capabilities

## 🚨 MANDATORY WORKFLOW - NO EXCEPTIONS 🚨

### STEP 1: ALWAYS CHECK CURRENT GOALS FIRST
Before any goal operation, you MUST:
1. Call `list_goals` to understand the user's current goal landscape
2. Analyze existing goals for duplicates, conflicts, or patterns
3. Use this information to provide intelligent coaching

### STEP 2: TOOL USAGE REQUIREMENTS
- **CREATE operations**: Always check for duplicates first
- **UPDATE operations**: Verify goal exists and validate new data
- **DELETE operations**: Confirm with user before deletion
- **STATUS changes**: Validate state transitions (only one "in_progress" goal allowed)

### STEP 3: INTELLIGENT COACHING
- Provide context-aware recommendations based on existing goals
- Suggest realistic timelines and amounts based on user's goal history
- Identify potential conflicts or synergies between goals
- Offer personalized financial coaching advice

## CRITICAL BUG PREVENTION RULES

### DUPLICATE PREVENTION
**MANDATORY**: Before creating ANY new goal:
1. Call `list_goals` to check existing goals
2. Compare new goal against existing goals (title, category, nature, amount)
3. If similar goal exists, ask user: "I found a similar goal: [goal_title]. Would you like to update it instead?"
4. Wait for explicit user confirmation before creating duplicates

### STATUS TRANSITION VALIDATION
**MANDATORY**: For status changes to "in_progress":
1. Call `get_in_progress_goal` to check for existing active goal
2. If active goal exists, inform user: "You have an active goal: [goal_title]. Only one goal can be in progress."
3. Offer to pause current goal or modify the request

### DATA VALIDATION
- Validate all monetary amounts (positive numbers, proper currency)
- Ensure realistic timelines (start_date < end_date, reasonable duration)
- Verify category-nature combinations make sense
- Check frequency settings are appropriate for goal type

## RESPONSE GUIDELINES

### SUCCESS RESPONSES
- Provide clear confirmation of actions taken
- Include relevant goal details in user-friendly format
- Offer next steps or recommendations
- Reference related goals when appropriate

### ERROR HANDLING
- Explain what went wrong in plain language
- Suggest corrective actions
- Provide alternative approaches when possible
- Never expose technical error details to users

### COACHING INTEGRATION
- Connect goal management to broader financial wellness
- Provide motivational and educational content
- Suggest goal optimization strategies
- Reference user's progress and achievements

## EXAMPLES

### Creating a Goal
```
User: "I want to save $5000 for an emergency fund"

Response:
1. Call list_goals() to check existing goals
2. If no emergency fund goal exists:
   - Create goal with appropriate defaults
   - Explain importance of emergency funds
   - Suggest timeline based on user's income (if known)
3. If similar goal exists:
   - Ask about updating vs creating new goal
   - Explain the difference if user wants both
```

### Goal Status Management
```
User: "Set my vacation goal to active"

Response:
1. Call get_in_progress_goal() to check current active goal
2. If another goal is active:
   - Inform user about the limitation
   - Offer to pause current goal
   - Explain benefits of focused goal pursuit
3. If no conflicts, proceed with status change
```

## TOOL REFERENCE

Available tools for goal management:
- `create_goal`: Create new financial goal
- `update_goal`: Modify existing goal
- `list_goals`: Get all user goals
- `get_goal_by_id`: Get specific goal details
- `get_in_progress_goal`: Get currently active goal
- `switch_goal_status`: Change goal status
- `delete_goal`: Remove goal (soft delete)

Remember: You are providing analysis to the supervisor. Focus on thorough goal analysis and actionable recommendations.
"""

    # Add user context if provided
    if user_context:
        context_section = "\n## USER CONTEXT\n"
        for key, value in user_context.items():
            context_section += f"- {key}: {value}\n"
        base_prompt += context_section

    return base_prompt.strip()

# Keep existing GOAL_AGENT_PROMPT for backwards compatibility during migration
GOAL_AGENT_PROMPT_RAW = build_goal_system_prompt()

def sanitize_prompt(prompt: str) -> str:
    """Sanitize prompt to avoid tokenization issues."""
    sanitized = prompt.replace("≥", ">=").replace("≤", "<=")
    sanitized = sanitized.replace("→", "->").replace("✅", "[SUCCESS]")
    return sanitized.encode('utf-8', errors='ignore').decode('utf-8')

GOAL_AGENT_PROMPT = sanitize_prompt(GOAL_AGENT_PROMPT_RAW)
```

### Step 6: Update App State

**Add to `app/core/app_state.py`**:

```python
# Add goal agent graph functions
def get_goal_agent_graph():
    """Get the compiled goal agent graph."""
    from app.agents.supervisor.goal_agent.agent import compile_goal_agent_graph
    
    return compile_goal_agent_graph()

def get_goal_agent():
    """Get goal agent instance."""
    from app.agents.supervisor.goal_agent.agent import GoalAgent
    
    global _goal_agent
    if _goal_agent is None:
        _goal_agent = GoalAgent()
    return _goal_agent

# Add global variable
_goal_agent = None
```

### Step 7: Update Workers Integration

**Update `app/agents/supervisor/workers.py`**:

```python
async def goal_agent(state: MessagesState, config: RunnableConfig) -> dict[str, Any]:
    """Goal agent worker that handles financial goals management."""
    try:
        from app.core.app_state import get_goal_agent_graph

        goal_graph = get_goal_agent_graph()
        logger.info("Using goal_agent_graph instance")

        user_id = get_config_value(config, "user_id")

        # Create unique thread for each supervisor handoff to ensure clean state
        import uuid
        unique_thread_id = f"goal-task-{uuid.uuid4()}"
        
        goal_config = {
            "configurable": {
                "thread_id": unique_thread_id,
                "user_id": user_id
            }
        }

        result = await goal_graph.ainvoke(state, config=goal_config)

        goal_response = ""
        if "messages" in result and isinstance(result["messages"], list):
            for msg in reversed(result["messages"]):
                if (hasattr(msg, "content") and
                    getattr(msg, "name", None) == "goal_agent" and
                    not getattr(msg, "response_metadata", {}).get("is_handoff_back", False) and
                    "Returning control to supervisor" not in str(msg.content)):
                    goal_response = str(msg.content)
                    break

        if not goal_response.strip():
            goal_response = "Goal analysis completed successfully."

        from app.agents.supervisor.handoff import create_handoff_back_messages
        handoff_messages = create_handoff_back_messages("goal_agent", "supervisor")

        return {
            "messages": [
                {"role": "assistant", "content": goal_response, "name": "goal_agent"},
                handoff_messages[0],
            ]
        }

    except Exception as e:
        logger.error("Error in goal_agent: %s", e)
        return {
            "messages": [{
                "role": "assistant",
                "content": f"I'm sorry, I had a problem processing your goal request: {str(e)}",
                "name": "goal_agent"
            }]
        }
```

## Migration Checklist

### Phase 1: Preparation
- [ ] **Backup existing goal agent code**
- [ ] **Create new goal_agent directory structure**
- [ ] **Implement GoalAgent class with modern patterns**
- [ ] **Create subgraph.py with multi-node architecture**
- [ ] **Add helpers.py with utility functions**
- [ ] **Enhance prompts.py with mandatory workflow**

### Phase 2: Integration
- [ ] **Update app_state.py with goal agent functions**
- [ ] **Modify workers.py with unique thread IDs**
- [ ] **Test new architecture in isolation**
- [ ] **Validate tool functionality**
- [ ] **Check response cleaning logic**

### Phase 3: Supervisor Updates
- [ ] **Verify supervisor handoff tool registration**
- [ ] **Test supervisor delegation flow**
- [ ] **Validate state isolation between tasks**
- [ ] **Check error handling paths**
- [ ] **Test multiple goal operations in sequence**

### Phase 4: Testing & Validation
- [ ] **Unit tests for new components**
- [ ] **Integration tests for supervisor flow**
- [ ] **Performance testing vs old architecture**
- [ ] **User acceptance testing**
- [ ] **Load testing with concurrent users**

### Phase 5: Deployment
- [ ] **Feature flag implementation**
- [ ] **Gradual rollout strategy**
- [ ] **Monitor error rates and performance**
- [ ] **User feedback collection**
- [ ] **Rollback plan preparation**

### Phase 6: Cleanup
- [ ] **Remove old singleton code**
- [ ] **Clean up unused imports**
- [ ] **Update documentation**
- [ ] **Archive old code for reference**

## Testing Strategy

### 1. Unit Testing
```python
# Test individual components
def test_goal_agent_initialization():
    agent = GoalAgent()
    assert agent.llm is not None

def test_response_cleaning():
    # Test _clean_response function
    pass

def test_tool_call_limiting():
    # Test tool call limits
    pass
```

### 2. Integration Testing
```python
# Test supervisor integration
async def test_supervisor_delegation():
    # Test full delegation flow
    pass

async def test_state_isolation():
    # Test unique thread IDs
    pass
```

### 3. Performance Testing
- Compare response times: old vs new architecture
- Memory usage analysis
- Concurrent user testing
- Tool execution performance

### 4. User Acceptance Testing
- Goal CRUD operations
- Duplicate prevention
- Status transition validation
- Error handling scenarios

## Rollback Plan

### 1. Immediate Rollback (< 5 minutes)
- Change feature flag to use old singleton
- No code deployment needed

### 2. Code Rollback (< 30 minutes)
- Revert workers.py changes
- Revert app_state.py changes
- Keep new code for future migration

### 3. Full Rollback (< 2 hours)
- Remove new goal_agent directory
- Restore original singleton patterns
- Update supervisor configuration

## Benefits of Migration

### 1. **Consistency**
- ✅ Align with wealth agent patterns
- ✅ Standardized architecture across agents
- ✅ Consistent error handling

### 2. **Reliability**
- ✅ State isolation between supervisor tasks
- ✅ Response quality control
- ✅ Tool call limiting

### 3. **Maintainability**
- ✅ Modern LangGraph patterns
- ✅ Clear separation of concerns
- ✅ Easier debugging and testing

### 4. **Performance**
- ✅ No singleton locking overhead
- ✅ Fresh state for each task
- ✅ Better memory management

### 5. **Scalability**
- ✅ No shared state bottlenecks
- ✅ Better concurrent user support
- ✅ Easier horizontal scaling

## Risk Mitigation

### 1. **Data Loss Prevention**
- Existing goal data remains unchanged
- CRUD tools remain identical
- Database schema unchanged

### 2. **User Experience**
- Gradual rollout with feature flags
- Fallback to old system if needed
- Extensive testing before deployment

### 3. **Performance Risks**
- Parallel testing to compare performance
- Load testing before full deployment
- Monitoring and alerting setup

## Post-Migration Tasks

### 1. **Monitoring**
- Set up dashboards for new architecture
- Monitor error rates and performance
- Track user engagement metrics

### 2. **Documentation**
- Update developer documentation
- Create troubleshooting guides
- Document lessons learned

### 3. **Team Training**
- Train team on new architecture
- Update debugging procedures
- Share best practices

---

This migration guide provides a comprehensive path to modernize the Goal Agent while maintaining functionality and ensuring a smooth transition. The new architecture will provide better reliability, consistency, and maintainability while enabling future enhancements.