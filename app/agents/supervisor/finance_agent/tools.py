from __future__ import annotations

import logging
import re
from typing import Optional
from uuid import UUID

from langchain_core.tools import tool

from app.repositories.database_service import get_database_service

logger = logging.getLogger(__name__)


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
    dangerous_keywords = [
        "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER",
        "TRUNCATE", "REPLACE", "MERGE", "CALL", "EXEC", "GRANT", "REVOKE"
    ]
    for keyword in dangerous_keywords:
        if re.search(rf"\b{keyword}\b", query_upper):
            return f"Only SELECT queries are allowed. Found dangerous keyword: {keyword}"

    # Disallow locking clauses which can block writers / change row locks
    if re.search(r"\bFOR\s+(UPDATE|NO\s+KEY\s+UPDATE|SHARE|KEY\s+SHARE)\b", query_upper):
        return "Row-level locks are not allowed (FOR UPDATE/SHARE)"

    # Disallow SELECT INTO (creates table in Postgres)
    if re.search(r"^\s*SELECT[\s\S]*?\bINTO\b\s+\w+", query_upper):
        return "SELECT INTO is not allowed"

    # Disallow data-modifying CTEs (WITH ... INSERT/UPDATE/DELETE ...)
    if query_upper.startswith("WITH") and re.search(r"\bWITH\b[\s\S]*\b(INSERT|UPDATE|DELETE|MERGE)\b", query_upper):
        return "Data-modifying CTEs are not allowed"

    # Ensure top-level statement is SELECT/CTE
    if not re.match(r"^\s*(SELECT|WITH)\b", query_upper, re.IGNORECASE):
        return "Only SELECT queries (including WITH CTEs) are allowed"

    # User isolation check
    if ":user_id" in query:
        return None

    user_id_pattern = rf"user_id\s*=\s*['\"]?{re.escape(str(user_id))}['\"]?"
    if re.search(user_id_pattern, query, re.IGNORECASE):
        return None

    where_pattern = r"WHERE.*user_id"
    if re.search(where_pattern, query, re.IGNORECASE):
        return None

    return "Query must include user_id filter for security"


@tool
async def sql_db_query(query: str) -> str:
    """Execute SQL query against the financial database with user isolation."""
    try:
        # This tool expects user_id to be passed from the agent context
        # The agent will handle user_id validation and injection
        logger.info(f"SQL query tool called with: {query[:100]}...")
        return f"Query executed: {query}"  # Placeholder - actual execution handled in agent
    except Exception as e:
        logger.error(f"SQL query tool error: {e}")
        return f"Error: {str(e)}"



async def execute_financial_query(query: str, user_id: UUID) -> str:
    """Execute SQL query against the financial database with user isolation."""
    db_service = get_database_service()

    try:
        logger.info(f"Starting database session creation for user {user_id}")
        async with db_service.get_session() as session:
            try:
                logger.info(f"Database session established, executing SQL for user {user_id}")

                security_error = _validate_query_security(query, user_id)
                if security_error:
                    return f"ERROR: {security_error}"

                # Create repository instance with the session
                logger.info(f"Creating FinanceRepository for user {user_id}")
                repo = db_service.get_finance_repository(session)

                # Execute the query
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
