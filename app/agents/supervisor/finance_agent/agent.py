from __future__ import annotations

import datetime
import logging
from typing import Any, Optional
from uuid import UUID

from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, RunnableConfig

from app.agents.supervisor.finance_agent.tools import execute_financial_query
from app.agents.supervisor.handoff import create_handoff_back_messages
from app.core.app_state import (
    get_cached_finance_agent,
    get_finance_agent,
    get_finance_samples,
    set_cached_finance_agent,
    set_finance_samples,
)
from app.core.config import config
from app.repositories.database_service import get_database_service
from app.repositories.postgres.finance_repository import FinanceTables
from app.utils.tools import get_config_value

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


def _create_error_command(error_message: str) -> Command:
    """Create a standardized error Command with handoff back to supervisor."""
    handoff_messages = create_handoff_back_messages("finance_agent", "supervisor")
    return Command(
        update={
            "messages": [
                {"role": "assistant", "content": error_message, "name": "finance_agent"},
                handoff_messages[0]
            ]
        },
        goto="supervisor"
    )


class FinanceAgent:
    """Finance agent for querying Plaid financial data using tools."""

    SAMPLE_CACHE_TTL_SECONDS: int = 600
    MAX_TRANSACTION_SAMPLES: int = 2
    MAX_ACCOUNT_SAMPLES: int = 1

    def __init__(self):
        logger.info("Initializing FinanceAgent with Bedrock models")

        guardrails = {
            "guardrailIdentifier": config.FINANCIAL_AGENT_GUARDRAIL_ID,
            "guardrailVersion": config.FINANCIAL_AGENT_GUARDRAIL_VERSION,
            "trace": "enabled",
        }

        self.sql_generator = ChatBedrockConverse(
            model_id=config.FINANCIAL_AGENT_MODEL_ID,
            region_name=config.FINANCIAL_AGENT_MODEL_REGION,
            temperature=config.FINANCIAL_AGENT_TEMPERATURE,
            guardrail_config=guardrails,
        )

        logger.info("FinanceAgent initialization completed")
        self._sample_cache: dict[str, dict[str, Any]] = {}

    async def _fetch_shallow_samples(self, user_id: UUID) -> tuple[str, str]:
        """Fetch sample data for transactions and accounts.

        Returns compact JSON arrays as strings for embedding in the prompt.
        """
        try:
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

                acct_query = (
                    "SELECT a.id, a.name, a.account_type, a.account_subtype, a.institution_name, a.created_at "
                    f"FROM {FinanceTables.ACCOUNTS} a "
                    "WHERE a.user_id = :user_id "
                    f"ORDER BY a.created_at DESC LIMIT {self.MAX_ACCOUNT_SAMPLES}"
                )

                tx_rows = await repo.execute_query(tx_query, user_id=str(user_id))
                acct_rows = await repo.execute_query(acct_query, user_id=str(user_id))

                tx_rows_serialized = [self._serialize_sample_row(r) for r in (tx_rows or [])]
                acct_rows_serialized = [self._serialize_sample_row(r) for r in (acct_rows or [])]

                tx_json = self._rows_to_json(tx_rows_serialized)
                acct_json = self._rows_to_json(acct_rows_serialized)

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
            if hasattr(v, "is_finite"):
                serialized[k] = float(v)
            elif isinstance(v, datetime.date):
                serialized[k] = v.isoformat()
            elif isinstance(v, UUID) or hasattr(v, "__class__") and "UUID" in str(type(v)):
                serialized[k] = str(v)
            else:
                serialized[k] = v
        return serialized

    def _rows_to_json(self, rows: list[dict[str, Any]]) -> str:
        """Convert serialized rows to JSON string."""
        import json

        return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))

    async def _create_system_prompt(self, user_id: UUID) -> str:
        """Create the system prompt for the finance agent."""
        tx_samples, acct_samples = await self._fetch_shallow_samples(user_id)
        return f"""You are an AI text-to-SQL agent over the user's Plaid-mirrored PostgreSQL database. Your goal is to generate correct SQL, execute it via tools, and present a concise, curated answer.

        🚨 AGENT BEHAVIOR & CONTROL 🚨
        You are a SPECIALIZED ANALYSIS agent working under a supervisor. You are NOT responding directly to users.
        Your role is to:
        1. Execute financial queries efficiently - match thoroughness to task complexity
        2. Return findings appropriate to the task scope
        3. Focus on accuracy and efficiency over exhaustive analysis
        4. Your supervisor will format the final user-facing response
        5. If the task requests a single metric (e.g., total or count), compute it with ONE optimal query and STOP.

        You are receiving this task from your supervisor agent. Match your analysis thoroughness to what the task specifically asks for.

        🛠️ TOOL USAGE MANDATE 🛠️
        Respect ONLY the two typed schemas below as the source of truth. Do NOT run schema discovery or connectivity probes (e.g., SELECT 1). Assume the database is connected.

        **QUERY STRATEGY**: Prefer complex, comprehensive SQL queries that return complete results in one call over multiple simple queries. Use CTEs, joins, and advanced SQL features to get all needed data efficiently. The database is much faster than agent round-trips.

        🚨 EXECUTION LIMITS 🚨
        **MAXIMUM 5 DATABASE QUERIES TOTAL per analysis**
        **PLAN EFFICIENTLY - Prefer fewer queries when possible**
        **NO WASTEFUL ITERATION - Each query should provide unique, necessary data**

        📊 QUERY STRATEGY 📊
        Plan your queries strategically: use complex SQL with CTEs, joins, and aggregations to maximize data per query.
        Group related data needs together to minimize total queries.

        **EFFICIENT APPROACH:**
        1. Analyze what data you need (balances, transactions by category, spending patterns, etc.)
        2. Group related data requirements to minimize queries (e.g., combine multiple metrics in one query)
        3. Use advanced SQL features (CTEs, window functions) to get comprehensive results per query
        4. Execute 2-5 queries maximum, then analyze all results together
        5. Provide final answer based on complete dataset

        ## 🎯 Core Principles

        **EFFICIENCY FIRST**: Maximize data per query using complex SQL - database calls are expensive
        **STRATEGIC PLANNING**: Group data needs to use fewer queries, not more
        **STOP AT 5**: Never exceed 5 queries per analysis - redesign approach if needed
        4. **RESULT ANALYSIS**: Interpret the complete dataset comprehensively and extract meaningful insights
        5. **TASK-APPROPRIATE RESPONSE**: Match thoroughness to requirements but prefer efficient, comprehensive queries
        6. **EXTREME PRECISION**: Adhere to ALL rules and criteria literally - do not make assumptions
        7. **USER CLARITY**: State the date range used in the analysis
        8. **DATA VALIDATION**: State clearly if you don't have sufficient data - DO NOT INVENT INFORMATION
        9. **PRIVACY FIRST**: Never return raw SQL queries or raw tool output
        10. **NO GREETINGS/NO NAMES**: Do not greet. Do not mention the user's name. Answer directly.
        11. **NO COMMENTS**: Do not include comments in the SQL queries.
        12. **STOP AFTER ANSWERING**: Once you have sufficient data to answer the core question, provide your analysis immediately.

        ## 📌 Assumptions & Scope Disclosure (MANDATORY)

        Always append a short "Assumptions & Scope" section at the end of your analysis that explicitly lists:
        - Timeframe used: [start_date – end_date]. If the user did not specify a timeframe, assume a default reporting window of the most recent 30 days and mark it as "assumed".
        - Any assumptions that materially impact results, explained in plain language (e.g., "very few transactions in this period" or "merchant names were normalized for consistency").
        - Known limitations relevant to the user (e.g., "no transactions in the reporting window").

        Strictly PROHIBITED in this section and anywhere in outputs:
        - Any SQL, table/column names, functions, operators, pattern matches, or schema notes
        - Phrases like "as per schema", code snippets, or system/tool internals

        Keep this section concise (max 3 bullets) and user-facing only.

        ## 📊 Table Information & Rules

        Use the following typed table schemas as the definitive source of truth. Do NOT perform schema discovery or validation queries. Design filtering and aggregation logic based solely on these schemas.

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

        1. **Understand Question:** Analyze user's request thoroughly and identify ALL data requirements upfront
        2. **Identify Tables & Schema:** Consult schema for relevant tables and columns
        3. **Plan Comprehensive Query:** Design ONE complex SQL query using CTEs/joins to get all needed data
        4. **Formulate Query:** Generate syntactically correct, comprehensive SQL with proper security filtering
        5. **Verify Query:** Double-check syntax, logic, and security requirements
        6. **Execute Query:** Execute using sql_db_query tool (prefer 1-2 comprehensive queries maximum)
        7. **Error Handling:** If queries fail due to syntax errors, fix them. If network/database errors, report clearly.
        8. **Analyze Complete Results & Formulate Direct Answer:**
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

        Today's date: {datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")}"""

    async def _create_agent_with_tools(self, user_id: UUID):
        """Create a manual ReAct agent that always returns to supervisor."""
        logger.info(f"Creating financial agent for user {user_id}")

        @tool
        async def sql_db_query(query: str) -> str:
            """Execute a single read-only SQL query for this user's data."""
            return await execute_financial_query(query, user_id)

        tools = [sql_db_query]
        tool_node = ToolNode(tools)

        model_with_tools = self.sql_generator.bind_tools(tools)

        async def agent_node(state: MessagesState):
            system_prompt = await self._create_system_prompt(user_id)
            messages = [{"role": "system", "content": system_prompt}] + state["messages"]
            response = await model_with_tools.ainvoke(messages)
            return {"messages": [response]}

        def supervisor_node(state: MessagesState):
            """Node that extracts analysis results and routes back to parent supervisor."""
            analysis_content = ""

            for msg in reversed(state["messages"]):
                if (hasattr(msg, "role") and msg.role == "assistant" and
                    hasattr(msg, "content") and msg.content):
                    if isinstance(msg.content, list):
                        for content_block in msg.content:
                            if isinstance(content_block, dict) and content_block.get("type") == "text":
                                analysis_content = content_block.get("text", "")
                                break
                    else:
                        analysis_content = msg.content
                    break

            analysis_response = f"""
            FINANCIAL ANALYSIS COMPLETE:

            Analysis Results:
            {analysis_content}

            This analysis is provided to the supervisor for final user response formatting.
            """

            handoff_messages = create_handoff_back_messages("finance_agent", "supervisor")

            return Command(
                update={
                    "messages": [
                        {"role": "assistant", "content": analysis_response, "name": "finance_agent"},
                        handoff_messages[0]
                    ]
                },
                goto="supervisor"
            )

        def should_continue(state: MessagesState):
            last_message = state["messages"][-1]
            if last_message.tool_calls:
                return "tools"
            return "supervisor"

        workflow = StateGraph(MessagesState)
        workflow.add_node("agent", agent_node)
        workflow.add_node("tools", tool_node)
        workflow.add_node("supervisor", supervisor_node)

        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges("agent", should_continue)
        workflow.add_edge("tools", "agent")

        return workflow.compile()


    async def process_query_with_agent(self, query: str, user_id: UUID) -> Command:
        """Process financial queries and return the Command from agent execution."""
        try:
            logger.info(f"Processing finance query with agent for user {user_id}: {query}")

            agent = get_cached_finance_agent(user_id)
            if agent is None:
                agent = await self._create_agent_with_tools(user_id)
                set_cached_finance_agent(user_id, agent)
            else:
                logger.info(f"Using cached LangGraph agent for user {user_id}")

            messages = [HumanMessage(content=query)]

            logger.info(f"Starting LangGraph agent execution for user {user_id}")
            agent_command = await agent.ainvoke({"messages": messages}, config={"recursion_limit": 10})
            logger.info(f"Agent execution completed for user {user_id}")

            return agent_command

        except Exception as e:
            logger.error(f"Finance agent error for user {user_id}: {e}")
            return _create_error_command("I encountered an error while processing your financial query. Please try again.")


async def finance_agent(state: MessagesState, config: RunnableConfig) -> Command:
    """LangGraph node for finance agent that provides analysis to supervisor."""
    try:
        user_id = get_config_value(config, "user_id")
        if not user_id:
            user_id = _get_user_id_from_messages(state["messages"])

        query = _get_last_user_message_text(state["messages"])
        logger.info(f"Finance agent - user_id: {user_id}, task: {query[:100]}...")

        if not user_id:
            logger.warning("No user_id found in finance agent request")
            return _create_error_command("ERROR: Cannot access financial data without user identification.")

        if not query:
            logger.warning("No task description found in finance agent request")
            return _create_error_command("ERROR: No task description provided for analysis.")

        finance_agent_instance = get_finance_agent()
        agent_command = await finance_agent_instance.process_query_with_agent(query, user_id)

        return agent_command

    except Exception as e:
        logger.error(f"Finance agent critical error: {e}")
        error_analysis = f"FINANCIAL ANALYSIS ERROR: {str(e)}"

        handoff_messages = create_handoff_back_messages("finance_agent", "supervisor")

        return Command(
            update={
                "messages": [
                    {"role": "assistant", "content": error_analysis, "name": "finance_agent"},
                    handoff_messages[0]
                ]
            },
            goto="supervisor"
        )
