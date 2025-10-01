from __future__ import annotations

import logging
import re
from typing import Any, Final, Optional, Pattern
from uuid import UUID

from langchain_core.tools import tool

from app.repositories.database_service import get_database_service
from app.services.external_context.http_client import FOSHttpClient

logger = logging.getLogger(__name__)


CONNECTIVITY_PROBE_PATTERNS: Final[list[Pattern[str]]] = [
    re.compile(r"^\s*SELECT\s+1(\s+AS\b[\w\d_]+)?\s*;?\s*$", re.IGNORECASE),
    re.compile(r"^\s*SELECT\s+NOW\(\)\s*;?\s*$", re.IGNORECASE),
    re.compile(r"^\s*SELECT\s+VERSION\(\)\s*;?\s*$", re.IGNORECASE),
]

DANGEROUS_SQL_KEYWORDS: Final[tuple[str, ...]] = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "CREATE",
    "ALTER",
    "TRUNCATE",
    "REPLACE",
    "MERGE",
    "CALL",
    "EXEC",
    "GRANT",
    "REVOKE",
)

LOCKING_CLAUSE_REGEX: Final[Pattern[str]] = re.compile(
    r"\bFOR\s+(UPDATE|NO\s+KEY\s+UPDATE|SHARE|KEY\s+SHARE)\b",
    re.IGNORECASE,
)

SELECT_INTO_REGEX: Final[Pattern[str]] = re.compile(
    r"^\s*SELECT[\s\S]*?\bINTO\b\s+\w+",
    re.IGNORECASE,
)

DATA_MODIFYING_CTE_REGEX: Final[Pattern[str]] = re.compile(
    r"\bWITH\b[\s\S]*\b(INSERT|UPDATE|DELETE|MERGE)\b",
    re.IGNORECASE,
)

TOP_LEVEL_ALLOWED_REGEX: Final[Pattern[str]] = re.compile(
    r"^\s*(SELECT|WITH)\b",
    re.IGNORECASE,
)

COUNT_PRECHECK_REGEX: Final[Pattern[str]] = re.compile(
    r"^SELECT\s+COUNT\(\*\)\s+AS\s+\w+\s+FROM\s+",
    re.IGNORECASE,
)

WHERE_USER_ID_REGEX: Final[Pattern[str]] = re.compile(r"WHERE.*user_id", re.IGNORECASE)


def _validate_query_security(query: str, user_id: UUID) -> Optional[str]:
    """Validate that the SQL is read-only and properly user-scoped.

    Rules:
    - Only allow SELECT and WITH (CTE) queries
    - Disallow DML/DDL keywords anywhere (INSERT/UPDATE/DELETE/..)
    - Disallow locking clauses (FOR UPDATE/SHARE)
    - Disallow SELECT INTO (creates table)
    - Require user_id filter for isolation
    """
    # Strip comments first
    cleaned = re.sub(r"--.*$", "", query, flags=re.MULTILINE)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)

    # Strip common string literal forms to avoid false positives
    cleaned = re.sub(r"'(?:''|[^'])*'", "''", cleaned)  # single-quoted strings
    cleaned = re.sub(r'"(?:""|[^"])*"', '""', cleaned)  # double-quoted identifiers/strings
    cleaned = re.sub(r"\$[a-zA-Z0-9_]*\$[\s\S]*?\$[a-zA-Z0-9_]*\$", "$$$$", cleaned)  # dollar-quoted

    query_upper = cleaned.upper().strip()

    # Disallow dangerous operations anywhere
    for keyword in DANGEROUS_SQL_KEYWORDS:
        if re.search(rf"\b{keyword}\b", query_upper):
            return f"Only SELECT queries are allowed. Found dangerous keyword: {keyword}"

    # Disallow locking clauses which can block writers / change row locks
    if LOCKING_CLAUSE_REGEX.search(query_upper):
        return "Row-level locks are not allowed (FOR UPDATE/SHARE)"

    # Disallow SELECT INTO (creates table in Postgres)
    if SELECT_INTO_REGEX.search(query_upper):
        return "SELECT INTO is not allowed"

    # Disallow data-modifying CTEs (WITH ... INSERT/UPDATE/DELETE ...)
    if query_upper.startswith("WITH") and DATA_MODIFYING_CTE_REGEX.search(query_upper):
        return "Data-modifying CTEs are not allowed"

    # Ensure top-level statement is SELECT/CTE
    if not TOP_LEVEL_ALLOWED_REGEX.match(query_upper):
        return "Only SELECT queries (including WITH CTEs) are allowed"

    # User isolation check
    if ":user_id" in query:
        return None

    user_id_pattern = rf"user_id\s*=\s*['\"]?{re.escape(str(user_id))}['\"]?"
    if re.search(user_id_pattern, query, re.IGNORECASE):
        return None

    if WHERE_USER_ID_REGEX.search(query):
        return None

    return "Query must include user_id filter for security"


def create_sql_db_query_tool(user_id):
    """Create a user-scoped SQL query tool."""
    @tool
    async def sql_db_query(query: str) -> str:
        """Execute a single read-only SQL query for this user's data."""
        return await execute_financial_query(query, user_id)

    return sql_db_query


def create_net_worth_summary_tool(user_id: UUID):
    """Create a tool that fetches canonical net worth data from FOS service."""
    client = FOSHttpClient()

    @tool
    async def net_worth_summary() -> dict[str, Any]:
        """Return canonical net worth summary (assets, liabilities, net worth)."""
        endpoint = f"/internal/financial/reports/net-worth?user_id={user_id}"
        response = await client.get(endpoint)
        if response is None:
            return {"error": "Failed to fetch net worth report from FOS service."}
        return response

    return net_worth_summary


async def execute_financial_query(query: str, user_id: UUID) -> str:
    """Execute SQL query against the financial database with user isolation."""
    db_service = get_database_service()

    try:
        logger.info(f"Starting database session creation for user {user_id}")
        async with db_service.get_session() as session:
            try:
                logger.info(f"Database session established, executing SQL for user {user_id}")

                # Block common connectivity probes with hard error
                if any(p.match(query) for p in CONNECTIVITY_PROBE_PATTERNS):
                    logger.info("Connectivity probe detected; blocking")
                    return "ERROR: Connectivity probes are forbidden. Execute the main query directly."

                # Block COUNT(*) pre-checks without GROUP BY (existence tests)
                normalized = re.sub(r"\s+", " ", query.strip(), flags=re.MULTILINE)
                if COUNT_PRECHECK_REGEX.match(normalized) and " GROUP BY " not in normalized.upper():
                    logger.info("COUNT(*) pre-check detected; blocking")
                    return "ERROR: Pre-check COUNT(*) queries are forbidden. Compute the metric directly in one statement."

                security_error = _validate_query_security(query, user_id)
                if security_error:
                    return f"ERROR: {security_error}"

                repo = db_service.get_finance_repository(session)

                logger.info(f"Executing query via repository for user {user_id}")
                result = await repo.execute_query(query, user_id=str(user_id))

                if not result:
                    return "No data found for your query."

                logger.info(f"Query executed successfully for user {user_id}, returning {len(result)} results to agent")
                return result

            except Exception as exec_error:
                logger.error(f"SQL execution error for user {user_id}: {exec_error}")
                await session.rollback()
                return f"Error executing query: {str(exec_error)}"

    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        return f"Error: {str(e)}"
