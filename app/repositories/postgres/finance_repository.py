from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class FinanceTables:
    """Constants for finance-related database tables."""

    ACCOUNTS = "public.unified_accounts"
    TRANSACTIONS = "public.unified_transactions"


class FinanceRepository:
    """PostgreSQL repository for finance data queries against Plaid tables."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def user_has_any_accounts(self, user_id: UUID) -> bool:
        """Return True if the user has any connected accounts, else False."""
        try:
            query = text(f"SELECT 1 FROM {FinanceTables.ACCOUNTS} WHERE user_id = :user_id LIMIT 1")
            result = await self.session.execute(query, {"user_id": str(user_id)})
            return bool(result.first())
        except Exception as exec_error:
            logger.error(f"Check accounts existence error for user {user_id}: {exec_error}")
            await self.session.rollback()
            return False

    async def execute_query(self, query: str, **parameters) -> Optional[list[dict]]:
        """Execute a SQL query with flexible parameters via kwargs."""
        try:
            logger.info(f"FinanceRepository executing SQL with params {parameters}: {query}...")

            # Enforce read-only at the database level for this transaction
            try:
                await self.session.execute(text("SET TRANSACTION READ ONLY"))
            except Exception as readonly_error:
                logger.warning(f"Failed to set transaction READ ONLY: {readonly_error}")

            # Execute the query with provided parameters
            logger.info(f"Sending query to database with params {parameters}")
            result = await self.session.execute(text(query), parameters)
            logger.info(f"Query executed, fetching results with params {parameters}")
            rows = result.fetchall()
            logger.info(f"Fetched {len(rows) if rows else 0} rows with params {parameters}")

            if not rows:
                return []

            # Convert to list of dictionaries
            formatted_rows = [dict(row._mapping) for row in rows]
            logger.info(f"Successfully formatted {len(formatted_rows)} rows with params {parameters}")
            return formatted_rows

        except Exception as exec_error:
            logger.error(f"SQL execution error with params {parameters}: {exec_error}")
            await self.session.rollback()
            raise exec_error
