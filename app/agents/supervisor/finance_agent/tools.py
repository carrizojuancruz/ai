from __future__ import annotations

import logging
from uuid import UUID

from langchain_core.tools import tool

from app.repositories.database_service import get_database_service

logger = logging.getLogger(__name__)


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

                # Parse and validate the query to ensure user_id filtering
                if ":user_id" not in query and "user_id =" not in query:
                    return "ERROR: Query must include user_id filter for security"

                # Create repository instance with the session
                logger.info(f"Creating FinanceRepository for user {user_id}")
                repo = db_service.get_finance_repository(session)

                # Execute the query
                logger.info(f"Executing query via repository for user {user_id}")
                result = await repo.execute_query(query, user_id)

                if not result:
                    return "No data found for your query."

                # Format results as readable text
                logger.info(f"Query executed successfully for user {user_id}, formatting {len(result)} results")
                formatted_result = f"Found {len(result)} results:\n" + "\n".join([
                    str(row) for row in result[:10]  # Limit to first 10 results
                ])
                logger.info(f"Query completed for user {user_id}, returning results")
                return formatted_result

            except Exception as exec_error:
                logger.error(f"SQL execution error for user {user_id}: {exec_error}")
                await session.rollback()
                return f"Error executing query: {str(exec_error)}"

    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        return f"Error: {str(e)}"
