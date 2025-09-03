from __future__ import annotations

import datetime
import logging
from typing import Any, Optional
from uuid import UUID

from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage
from langgraph.graph import MessagesState
from langgraph.prebuilt import create_react_agent
from langgraph.types import RunnableConfig

from app.core.config import config
from app.agents.supervisor.finance_agent.tools import sql_db_schema, execute_financial_query

logger = logging.getLogger(__name__)


def _extract_text_from_content(content) -> str:
    """Extract text content from various message formats."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                value = item.get("text") or item.get("content") or ""
                if isinstance(value, str):
                    parts.append(value)
        return "\n".join(parts).strip()
    return str(content) if content else ""


def _get_last_user_message_text(messages: list[HumanMessage | dict[str, Any]]) -> str:
    """Get the last user message text from the conversation."""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return _extract_text_from_content(getattr(m, "content", ""))
        if isinstance(m, dict) and m.get("role") == "user":
            return _extract_text_from_content(m.get("content"))
    return ""


def _get_user_id_from_messages(messages: list[HumanMessage | dict[str, Any]]) -> Optional[UUID]:
    """Extract user_id from messages if available."""
    for m in reversed(messages):
        if isinstance(m, dict) and m.get("role") == "user":
            user_id = m.get("user_id")
            if user_id:
                try:
                    return UUID(user_id) if isinstance(user_id, str) else user_id
                except (ValueError, TypeError):
                    continue
    return None


class FinanceAgent:
    """Finance agent for querying Plaid financial data using tools."""

    def __init__(self):
        logger.info("Initializing FinanceAgent with Bedrock models")

        # Initialize Bedrock models
        region = config.AWS_REGION
        sonnet_model_id = config.BEDROCK_MODEL_ID

        guardrails = {
            "guardrailIdentifier": config.BEDROCK_GUARDRAIL_ID,
            "guardrailVersion": config.BEDROCK_GUARDRAIL_VERSION,
            "trace": True,
        }

        logger.info(f"Creating Bedrock ChatBedrock client for model {sonnet_model_id}")

        # Primary model for SQL generation (Sonnet)
        self.sql_generator = ChatBedrock(
            model_id=sonnet_model_id,
            region_name=region,
            guardrails=guardrails
        )

        logger.info("FinanceAgent initialization completed")

    def _create_system_prompt(self, user_id: UUID) -> str:
        """Create the system prompt for the finance agent."""
        return f"""You are an AI text-to-SQL agent over the user's Plaid-mirrored PostgreSQL database. Your goal is to generate correct SQL, execute it via tools, and present a concise, curated answer.

        🚨 AGENT PERSISTENCE & CONTROL 🚨
        You are an agent - please keep going until the user's query is completely resolved, before ending your turn and yielding back to the user. Only terminate your turn when you are sure that all required SQL queries have been executed successfully and you have provided comprehensive insights based on the results.

        🛠️ TOOL USAGE MANDATE 🛠️
        If you are not sure about tables/columns, use tools to verify schema. Do NOT guess or invent SQL.

        📊 PLANNING & QUERY STRATEGY 📊
        You MUST plan carefully BEFORE generating SQL and reflect on results, but keep all planning INTERNAL.
        NEVER narrate your plan or process. Do NOT write phrases like "Let me", "I'll", "Understand the question", or step lists.

        1. **Analyze Requirements**: Break down the user's request into specific data requirements
        2. **Schema Verification**: Confirm table structures, column names, and relationships
        3. **Query Design**: Plan the optimal SQL structure before writing
        4. **Execution Strategy**: Determine if multiple queries are needed for complex requests
        5. **Result Analysis**: Interpret and synthesize query results into actionable insights

        ## 🎯 Core Objective & Principles

        1. **QUERY GENERATION**: Create syntactically correct SQL queries
        2. **TOOL EXECUTION**: Use available database tools systematically
        3. **RESULT ANALYSIS**: Interpret the data comprehensively and extract meaningful insights
        4. **COMPREHENSIVE RESPONSE**: Provide complete, formatted responses that fully address the user's query
        5. **EXTREME PRECISION**: Adhere to ALL rules and criteria literally - do not make assumptions
        6. **USER CLARITY**: State the date range used in the analysis
        7. **DATA VALIDATION**: State clearly if you don't have sufficient data - DO NOT INVENT INFORMATION
        8. **PRIVACY FIRST**: Never return raw SQL queries or raw tool output
        9. **NO GREETINGS/NO NAMES**: Do not greet. Do not mention the user's name. Answer directly.

        ## 📊 Table Information & Rules

        **Schema Planning Protocol**: Before writing queries:
        1. Identify which tables contain the required data
        2. Verify column names and data types using tools if uncertain
        3. Plan join strategies if multiple tables are needed
        4. Design filtering and aggregation logic

        ## ❗ Mandatory Security & Filtering Rules

        **SECURITY REQUIREMENTS (APPLY TO ALL QUERIES):**
        1. **User Isolation**: **ALWAYS** include `WHERE user_id = '{user_id}'` in ALL queries
        2. **Never Skip**: **NEVER** allow queries without user_id filter for security
        3. **Multiple Conditions**: If using joins, ensure user_id filter is applied to the appropriate table

        ## 📋 TABLE SCHEMAS

        **public.unified_accounts:**
        - id (UUID): Primary key
        - user_id (UUID): User identifier (ALWAYS filter by this)
        - name (VARCHAR): Account name
        - account_type (VARCHAR): Type (depository, credit, investment, loan)
        - account_subtype (VARCHAR): Subtype (checking, savings, credit_card, etc.)
        - current_balance (NUMERIC): Current balance
        - available_balance (NUMERIC): Available balance
        - total_value (NUMERIC): Total value
        - credit_limit (NUMERIC): Credit limit
        - available_credit (NUMERIC): Available credit
        - institution_name (VARCHAR): Bank/financial institution
        - currency_code (VARCHAR): Currency
        - is_active (BOOLEAN): Account is active
        - is_closed (BOOLEAN): Account is closed
        - created_at (TIMESTAMP): Creation date

        **public.unified_transactions:**
        - id (UUID): Primary key
        - user_id (UUID): User identifier (ALWAYS filter by this)
        - account_id (UUID): Reference to unified_accounts.id
        - amount (NUMERIC): Transaction amount (negative = spending, positive = income)
        - transaction_date (TIMESTAMP): Transaction date
        - name (VARCHAR): Transaction name
        - description (VARCHAR): Transaction description
        - merchant_name (VARCHAR): Merchant name
        - category (VARCHAR): Transaction category
        - category_detailed (VARCHAR): Detailed category
        - payment_channel (VARCHAR): Payment method
        - pending (BOOLEAN): Transaction is pending
        - created_at (TIMESTAMP): Record creation date

        ## ⚙️ Query Generation Rules

        **Pre-Query Planning Checklist:**
        ✅ Analyze user requirements completely
        ✅ Identify all needed tables and columns
        ✅ Plan date range logic
        ✅ Design aggregation and grouping strategy
        ✅ Verify security filtering (user_id)

        1. **Default Date Range:** If no period specified, use data for the last 30 days. If no data is found, ASK whether to expand the window before doing so.
        2. **Table Aliases:** Use short, intuitive aliases (e.g., `t` for transactions, `a` for accounts)
        3. **Select Relevant Columns:** Only select columns needed to answer the question
        4. **Aggregation Level:** Group by appropriate dimensions (date, category, merchant, etc.)
        5. **Default Ordering:** Order by date DESC unless another ordering is more relevant

        ## 🛠️ Standard Operating Procedure (SOP) & Response

        **Execute this procedure systematically for every request:**

        1. **Understand Question:** Analyze user's request thoroughly and break down requirements
        2. **Identify Tables & Schema:** Consult schema for relevant tables and columns
        3. **Plan Query Strategy:** Design the complete query approach before writing SQL
        4. **Formulate Query:** Generate syntactically correct SQL with proper security filtering
        5. **Verify Query:** Double-check syntax, logic, and security requirements
        6. **Execute Query:** Execute using sql_db_query tool
        7. **Error Handling:** If queries fail, analyze error, rewrite systematically, retry
        8. **Analyze Results & Formulate Insightful Answer:**
           * Provide a concise, curated answer (2–6 sentences) and, if helpful, a small table
           * Do NOT include plans/process narration
           * Do NOT echo raw tool responses or JSON. Summarize them instead
           * If empty results, say so briefly and propose a targeted next step (e.g., expand dates)
        9. **Privacy Protection:** Do not return raw queries or internal information
        10. **Data Validation:** State clearly if you don't have sufficient data

        ## 🔍 Query Validation Checklist
        Before executing any query, verify:
        ✅ Schema prefix (`public.`) on all tables
        ✅ User isolation filter applied (`WHERE user_id = '{user_id}'`)
        ✅ Date handling follows specification
        ✅ Aggregation and grouping logic is sound
        ✅ Column names match schema exactly

        Today's date: {datetime.datetime.now().strftime('%Y-%m-%d')}"""

    async def _create_agent_with_tools(self, user_id: UUID):
        """Create a LangGraph agent with SQL tools for the given user."""
        from langchain_core.tools import tool

        logger.info(f"Creating SQL tools for user {user_id}")

        # Create a custom sql_db_query tool that has access to user_id
        @tool
        async def sql_db_query(query: str) -> str:
            """Execute SQL query against the financial database."""
            return await execute_financial_query(query, user_id)

        # Create agent with tools
        tools = [sql_db_query, sql_db_schema]
        logger.info(f"Initializing LangGraph agent with tools for user {user_id}")

        agent = create_react_agent(
            model=self.sql_generator,
            tools=tools,
            prompt=self._create_system_prompt(user_id)
        )

        logger.info(f"LangGraph agent created successfully for user {user_id}")
        return agent

    async def process_query(self, query: str, user_id: UUID) -> str:
        """Main entry point for processing financial queries using tools."""
        try:
            logger.info(f"Processing finance query for user {user_id}: {query}")

            # Create agent with tools for this user
            agent = await self._create_agent_with_tools(user_id)
            logger.info(f"Successfully created agent with tools for user {user_id}")

            # Prepare the conversation
            messages = [
                HumanMessage(content=query)
            ]

            # Run the agent
            logger.info(f"Starting LangGraph agent execution for user {user_id}")
            result = await agent.ainvoke({"messages": messages})
            logger.info(f"Agent execution completed for user {user_id}, received {len(result['messages'])} messages")

            # Extract the final response
            final_message = result["messages"][-1]
            response_text = _extract_text_from_content(final_message.content)

            logger.info(f"Successfully processed finance query for user {user_id}")
            return response_text

        except Exception as e:
            logger.error(f"Finance agent error for user {user_id}: {e}")
            return "I encountered an error while processing your financial query. Please try again."


# Global finance agent instance
_finance_agent = FinanceAgent()


async def finance_agent(state: MessagesState, config: RunnableConfig) -> dict[str, Any]:
    """LangGraph node for finance agent."""
    try:

        # Get user_id from configurable context
        user_id = config.get("configurable", {}).get("user_id")
        if not user_id:
            # Fallback: try to extract from messages (preserved by handoff tool)
            user_id = _get_user_id_from_messages(state["messages"])

        query = _get_last_user_message_text(state["messages"])
        logger.info(f"Extracted user_id: {user_id}, query: {query[:50]}...")

        if not user_id:
            logger.warning("No user_id found in finance agent request")
            return {"messages": [{"role": "assistant", "content": "I need to know which user you are to access financial data.", "name": "finance_agent"}]}

        if not query:
            logger.warning("No query text found in finance agent request")
            return {"messages": [{"role": "assistant", "content": "What financial information would you like to know?", "name": "finance_agent"}]}

        logger.info(f"Delegating to finance agent process_query for user {user_id}")
        response = await _finance_agent.process_query(query, user_id)

        return {"messages": [{"role": "assistant", "content": response, "name": "finance_agent"}]}

    except Exception as e:
        logger.error(f"Finance agent critical error: {e}")
        return {"messages": [{"role": "assistant", "content": "I encountered an error processing your financial query. Please try again.", "name": "finance_agent"}]}
