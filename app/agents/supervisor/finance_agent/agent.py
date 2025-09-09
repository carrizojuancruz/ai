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

from app.agents.supervisor.finance_agent.tools import execute_financial_query
from app.core.config import config
from app.repositories.database_service import get_database_service
from app.repositories.postgres.finance_repository import FinanceTables

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

    SAMPLE_CACHE_TTL_SECONDS: int = 600
    MAX_TRANSACTION_SAMPLES: int = 2
    MAX_ACCOUNT_SAMPLES: int = 1

    def __init__(self):
        logger.info("Initializing FinanceAgent with Bedrock models")

        # Initialize Bedrock models
        region = config.AWS_REGION
        sonnet_model_id = config.BEDROCK_MODEL_ID

        guardrails = {
            "guardrailIdentifier": config.BEDROCK_GUARDRAIL_ID,
            "guardrailVersion": str(config.BEDROCK_GUARDRAIL_VERSION),
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
        # Lightweight per-user cache for prompt grounding samples
        self._sample_cache: dict[str, dict[str, Any]] = {}

    async def _fetch_shallow_samples(self, user_id: UUID) -> tuple[str, str]:
        """Fetch sample data for transactions and accounts.

        Returns compact JSON arrays as strings for embedding in the prompt.
        """
        try:
            from app.core.app_state import get_finance_samples, set_finance_samples

            cached_pair = get_finance_samples(user_id)
            if cached_pair:
                return cached_pair

            now = datetime.datetime.utcnow().timestamp()
            cache_key = str(user_id)
            cached = self._sample_cache.get(cache_key)
            if cached and (now - cached.get("cached_at", 0) < self.SAMPLE_CACHE_TTL_SECONDS):
                return cached.get("tx_samples", "[]"), cached.get("acct_samples", "[]")

            db_service = get_database_service()
            async with db_service.get_session() as session:
                repo = db_service.get_finance_repository(session)

                # Transaction sample
                tx_query = (
                    "SELECT "
                    "  t.external_transaction_id AS dedupe_id, "
                    "  t.amount, "
                    "  COALESCE(t.transaction_date::date, t.authorized_date::date) AS tx_date, "
                    "  COALESCE(NULLIF(t.merchant_name,''), NULLIF(t.name,'')) AS merchant, "
                    "  COALESCE(t.provider_tx_category_detailed, t.category_detailed, t.provider_tx_category, t.category, 'Uncategorized') AS category, "
                    "  t.pending, "
                    "  t.created_at "
                    f"FROM {FinanceTables.TRANSACTIONS} t "
                    "WHERE t.user_id = :user_id "
                    f"ORDER BY t.created_at DESC LIMIT {self.MAX_TRANSACTION_SAMPLES}"
                )

                # Account sample
                acct_query = (
                    "SELECT a.id, a.name, a.account_type, a.account_subtype, a.institution_name, a.created_at "
                    f"FROM {FinanceTables.ACCOUNTS} a "
                    "WHERE a.user_id = :user_id "
                    f"ORDER BY a.created_at DESC LIMIT {self.MAX_ACCOUNT_SAMPLES}"
                )

                tx_rows = await repo.execute_query(tx_query, user_id)
                acct_rows = await repo.execute_query(acct_query, user_id)

                # Convert PostgreSQL/SQLAlchemy types to JSON-serializable types
                tx_rows_serialized = [self._serialize_sample_row(r) for r in (tx_rows or [])]
                acct_rows_serialized = [self._serialize_sample_row(r) for r in (acct_rows or [])]

                tx_json = self._rows_to_json(tx_rows_serialized)
                acct_json = self._rows_to_json(acct_rows_serialized)

                # Cache
                self._sample_cache[cache_key] = {
                    "tx_samples": tx_json,
                    "acct_samples": acct_json,
                    "cached_at": now,
                }
                from contextlib import suppress
                with suppress(Exception):
                    set_finance_samples(user_id, tx_json, acct_json)
                return tx_json, acct_json
        except Exception as e:
            logger.warning(f"Error fetching samples: {e}")
            return "[]", "[]"

    def _serialize_sample_row(self, row) -> dict[str, Any]:
        """Serialize a database row to JSON-compatible format."""
        if not isinstance(row, dict):
            return row

        serialized = {}
        for k, v in row.items():
            if hasattr(v, 'is_finite'):  # Decimal
                serialized[k] = float(v)
            elif isinstance(v, datetime.date):  # date/datetime
                serialized[k] = v.isoformat()
            elif isinstance(v, UUID) or hasattr(v, '__class__') and 'UUID' in str(type(v)):  # UUID objects
                serialized[k] = str(v)
            else:
                serialized[k] = v
        return serialized

    def _rows_to_json(self, rows: list[dict[str, Any]]) -> str:
        """Convert serialized rows to JSON string."""
        import json
        return json.dumps(rows, ensure_ascii=False, separators=(',', ':'))

    async def _create_system_prompt(self, user_id: UUID) -> str:
        """Create the system prompt for the finance agent."""
        tx_samples, acct_samples = await self._fetch_shallow_samples(user_id)
        return f"""You are an AI text-to-SQL agent over the user's Plaid-mirrored PostgreSQL database. Your goal is to generate correct SQL, execute it via tools, and present a concise, curated answer.

        🚨 AGENT BEHAVIOR & CONTROL 🚨
        You are a SPECIALIZED ANALYSIS agent working under a supervisor. You are NOT responding directly to users.
        Your role is to:
        1. Execute financial queries and provide comprehensive data analysis
        2. Return detailed findings and insights to your supervisor
        3. Focus on accuracy, completeness, and actionable insights
        4. Your supervisor will format the final user-facing response

        You are receiving this task from your supervisor agent. Provide thorough analysis so they can create the best response for the user.

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

        ## 📋 TABLE SCHEMAS (Typed; shallow as source of truth)

        **{FinanceTables.TRANSACTIONS}**
        - id (UUID)
        - user_id (UUID)
        - account_id (UUID)
        - amount (NUMERIC)
        - transaction_date (TIMESTAMPTZ)
        - authorized_date (TIMESTAMPTZ)
        - name (TEXT)
        - merchant_name (VARCHAR)
        - category (VARCHAR)
        - category_detailed (VARCHAR)
        - provider_tx_category (VARCHAR)
        - provider_tx_category_detailed (VARCHAR)
        - payment_channel (VARCHAR)
        - pending (BOOLEAN)
        - external_transaction_id (VARCHAR)
        - created_at (TIMESTAMPTZ), updated_at (TIMESTAMPTZ)

        **{FinanceTables.ACCOUNTS}**
        - id (UUID)
        - user_id (UUID)
        - name (VARCHAR)
        - account_type (VARCHAR)
        - account_subtype (VARCHAR)
        - current_balance (NUMERIC)
        - available_balance (NUMERIC)
        - institution_name (VARCHAR)
        - created_at (TIMESTAMPTZ)

        ## 🧪 LIVE SAMPLE ROWS (internal; not shown to user)
        transactions_samples = {tx_samples}
        accounts_samples = {acct_samples}

        ## 🔧 NORMALIZATION CTE (reuse in queries; shallow-only)
        WITH base AS (
          SELECT
            t.user_id,
            t.account_id,
            t.external_transaction_id AS dedupe_id,
            t.amount,
            COALESCE(t.transaction_date::date, t.authorized_date::date) AS tx_date,
            COALESCE(NULLIF(t.merchant_name,''), NULLIF(t.name,'')) AS merchant,
            -- Enhanced category normalization with fallback chain
            CASE
              WHEN COALESCE(t.provider_tx_category_detailed, t.category_detailed, t.provider_tx_category, t.category) IS NOT NULL
              THEN COALESCE(t.provider_tx_category_detailed, t.category_detailed, t.provider_tx_category, t.category)
              ELSE 'Uncategorized'
            END AS category,
            t.pending,
            t.created_at
          FROM {FinanceTables.TRANSACTIONS} t
          WHERE t.user_id = '{user_id}'
        ),
        dedup AS (
          SELECT *, ROW_NUMBER() OVER (
            PARTITION BY dedupe_id ORDER BY tx_date DESC, created_at DESC
          ) AS rn
          FROM base
        )
        SELECT * FROM dedup WHERE rn = 1

        ## ⚙️ Query Generation Rules

        **Pre-Query Planning Checklist:**
        ✅ Analyze user requirements completely
        ✅ Identify all needed tables and columns
        ✅ Plan date range logic
        ✅ Design aggregation and grouping strategy
        ✅ Verify security filtering (user_id)

        1. **Default Date Range:** If no period specified, use data for the last 30 days (filter on tx_date). If no data is found for that period, state this clearly without expanding the search.
        2. **Table Aliases:** Use short, intuitive aliases (e.g., `d` for deduped tx, `a` for accounts)
        3. **Select Relevant Columns:** Only select columns needed to answer the question
        4. **Aggregation Level:** Group by appropriate dimensions (date, category, merchant, etc.)
        5. **Default Ordering:** Order by tx_date DESC unless another ordering is more relevant
        6. **Spending vs Income:** Spending amount > 0; Income amount < 0 (use shallow `amount`).
        7. **Category Ranking:** Rank categories by SUM(amount) DESC (not by distinct presence).
        8. **De-duplication:** Always use the `dedup` CTE and filter `rn = 1`.

        ## 🛠️ Standard Operating Procedure (SOP) & Response

        **Execute this procedure systematically for every request:**

        1. **Understand Question:** Analyze user's request thoroughly and break down requirements
        2. **Identify Tables & Schema:** Consult schema for relevant tables and columns
        3. **Plan Query Strategy:** Design the complete query approach before writing SQL
        4. **Formulate Query:** Generate syntactically correct SQL with proper security filtering
        5. **Verify Query:** Double-check syntax, logic, and security requirements
        6. **Execute Query:** Execute using sql_db_query tool
        7. **Error Handling:** If queries fail due to syntax errors, fix them. If network/database errors, report clearly.
        8. **Analyze Results & Formulate Direct Answer:**
           * Provide a concise, curated answer (2–6 sentences) and, if helpful, a small table
           * Do NOT include plans/process narration
           * Do NOT echo raw tool responses or JSON. Summarize them instead
           * **CRITICAL: If query returns 0 results, say so directly without retrying or exploring**
           * **Only retry/re-explore if user explicitly asks (e.g., "try a different date" or "expand search")**
        9. **Privacy Protection:** Do not return raw queries or internal information
        10. **Data Validation:** State clearly if you don't have sufficient data

        ## 🔍 Query Validation Checklist
        Before executing any query, verify:
        ✅ Schema prefix (`public.`) on all tables
        ✅ User isolation filter applied (`WHERE user_id = '{user_id}'`)
        ✅ Date handling follows specification
        ✅ Aggregation and grouping logic is sound
        ✅ Column names match schema exactly
        ✅ Amount sign convention verified (positive = spending)

        Today's date: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')}"""

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
        tools = [sql_db_query]
        logger.info(f"Initializing LangGraph agent with tools for user {user_id}")

        system_prompt = await self._create_system_prompt(user_id)
        agent = create_react_agent(
            model=self.sql_generator,
            tools=tools,
            prompt=system_prompt
        )

        logger.info(f"LangGraph agent created successfully for user {user_id}")
        return agent

    async def process_query(self, query: str, user_id: UUID) -> str:
        """Process financial queries using cached agent per user."""
        try:
            logger.info(f"Processing finance query for user {user_id}: {query}")

            from app.core.app_state import get_cached_finance_agent, set_cached_finance_agent

            agent = get_cached_finance_agent(user_id)
            if agent is None:
                logger.info(f"Creating new LangGraph agent for user {user_id}")
                agent = await self._create_agent_with_tools(user_id)
                set_cached_finance_agent(user_id, agent)
            else:
                logger.info(f"Using cached LangGraph agent for user {user_id}")

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




async def finance_agent(state: MessagesState, config: RunnableConfig) -> dict[str, Any]:
    """LangGraph node for finance agent that provides analysis to supervisor."""
    try:
        # Get user_id from configurable context
        user_id = config.get("configurable", {}).get("user_id")
        if not user_id:
            # Fallback: try to extract from messages (preserved by handoff tool)
            user_id = _get_user_id_from_messages(state["messages"])

        query = _get_last_user_message_text(state["messages"])
        logger.info(f"Finance agent - user_id: {user_id}, task: {query[:100]}...")

        if not user_id:
            logger.warning("No user_id found in finance agent request")
            error_msg = "ERROR: Cannot access financial data without user identification."
            return {"messages": [{"role": "assistant", "content": error_msg, "name": "finance_agent"}]}

        if not query:
            logger.warning("No task description found in finance agent request")
            error_msg = "ERROR: No task description provided for analysis."
            return {"messages": [{"role": "assistant", "content": error_msg, "name": "finance_agent"}]}

        # Process the financial analysis
        from app.core.app_state import get_finance_agent
        finance_agent_instance = get_finance_agent()
        analysis_result = await finance_agent_instance.process_query(query, user_id)

        analysis_response = f"""
        FINANCIAL ANALYSIS COMPLETE:

        Task Analyzed: {query[:200]}...

        Analysis Results:
        {analysis_result}

        This analysis is provided to the supervisor for final user response formatting.
        """

        from app.agents.supervisor.handoff import create_handoff_back_messages
        handoff_messages = create_handoff_back_messages("finance_agent", "supervisor")

        return {
            "messages": [
                {"role": "assistant", "content": analysis_response, "name": "finance_agent"},
                handoff_messages[0],  # AIMessage signaling completion
                handoff_messages[1],  # ToolMessage confirming return
            ]
        }

    except Exception as e:
        logger.error(f"Finance agent critical error: {e}")
        error_analysis = f"FINANCIAL ANALYSIS ERROR: {str(e)}"

        from app.agents.supervisor.handoff import create_handoff_back_messages
        handoff_messages = create_handoff_back_messages("finance_agent", "supervisor")

        return {
            "messages": [
                {"role": "assistant", "content": error_analysis, "name": "finance_agent"},
                handoff_messages[0],
                handoff_messages[1],
            ]
        }
