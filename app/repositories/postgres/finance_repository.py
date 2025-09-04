from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class FinanceRepository:
    """PostgreSQL repository for finance data queries against Plaid tables."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute_query(self, query: str, user_id: UUID) -> Optional[list[dict]]:
        """Execute a SQL query with user isolation."""
        try:
            logger.info(f"FinanceRepository executing SQL for user {user_id}: {query}...")

            # Execute the query with user_id parameter
            logger.info(f"Sending query to database for user {user_id}")
            result = await self.session.execute(text(query), {"user_id": str(user_id)})
            logger.info(f"Query executed, fetching results for user {user_id}")
            rows = result.fetchall()
            logger.info(f"Fetched {len(rows) if rows else 0} rows for user {user_id}")

            if not rows:
                return []

            # Convert to list of dictionaries
            column_names = result.keys() if hasattr(result, 'keys') else None
            if column_names:
                logger.info(f"Formatting results with columns: {list(column_names)}")
                formatted_rows = []
                for row in rows:
                    row_data = {col: getattr(row, col) for col in column_names}
                    formatted_rows.append(row_data)

                logger.info(f"Successfully formatted {len(formatted_rows)} rows for user {user_id}")
                return formatted_rows
            else:
                logger.info(f"Formatting results without column names for user {user_id}")
                formatted_rows = [dict(row) for row in rows]
                logger.info(f"Successfully formatted {len(formatted_rows)} rows for user {user_id}")
                return formatted_rows

        except Exception as exec_error:
            logger.error(f"SQL execution error for user {user_id}: {exec_error}")
            await self.session.rollback()
            raise exec_error
