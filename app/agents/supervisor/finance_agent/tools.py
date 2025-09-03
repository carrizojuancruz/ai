from __future__ import annotations

import logging
from typing import Optional
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


@tool
async def sql_db_schema(table_name: str) -> str:
    """Get schema information for a financial table."""
    try:
        if table_name == "unified_accounts":
            return """
public.unified_accounts:
- id (UUID): Primary key
- user_id (UUID): User identifier (CRITICAL: always filter by this)
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
"""
        elif table_name == "unified_transactions":
            return """
public.unified_transactions:
- id (UUID): Primary key
- user_id (UUID): User identifier (CRITICAL: always filter by this)
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
"""
        else:
            return f"Unknown table: {table_name}"
    except Exception as e:
        logger.error(f"Schema query error: {e}")
        return f"Error getting schema: {str(e)}"


async def execute_financial_query(query: str, user_id: UUID) -> str:
    """Execute SQL query against the financial database with user isolation."""
    db_service = get_database_service()

    try:
        logger.info(f"Starting database session creation for user {user_id}")
        async with db_service.get_session() as session:
            try:
                logger.info(f"Database session established, executing SQL for user {user_id}")
                logger.debug(f"Executing SQL for user {user_id}: {query}")

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
