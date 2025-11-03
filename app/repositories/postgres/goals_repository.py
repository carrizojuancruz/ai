"""Goals repository for database operations."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.supervisor.goal_agent.models import Goal
from app.observability.logging_config import get_logger

logger = get_logger(__name__)


class GoalsRepository:
    """Repository for goals database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_goal_by_id(self, goal_id: UUID) -> Optional[Goal]:
        """Get a single goal by ID."""
        query = text("""
            SELECT goal_id, user_id, version, goal_data, is_active, created_at, updated_at
            FROM public.goals
            WHERE goal_id = :goal_id AND is_active = true
        """)

        result = await self.session.execute(query, {"goal_id": str(goal_id)})
        row = result.fetchone()

        if not row:
            return None

        return self._row_to_goal(row)

    async def get_goals_by_user(self, user_id: UUID, is_active: bool = True) -> List[Goal]:
        """Get all goals for a user."""
        query = text("""
            SELECT goal_id, user_id, version, goal_data, is_active, created_at, updated_at
            FROM public.goals
            WHERE user_id = :user_id
            AND is_active = :is_active
            ORDER BY created_at DESC
        """)

        result = await self.session.execute(
            query, {"user_id": str(user_id), "is_active": is_active}
        )
        rows = result.fetchall()

        return [self._row_to_goal(row) for row in rows]

    async def get_active_goals_with_notifications(self) -> List[Goal]:
        """Get all active goals that have notifications enabled.

        Returns simple list - filtering logic is in GoalsService.
        """
        query = text("""
            SELECT goal_id, user_id, version, goal_data, is_active, created_at, updated_at
            FROM public.goals
            WHERE is_active = true
            AND (goal_data->>'notifications_enabled')::boolean = true
            ORDER BY created_at DESC
        """)

        result = await self.session.execute(query)
        rows = result.fetchall()

        goals = []
        for row in rows:
            try:
                goal = self._row_to_goal(row)
                goals.append(goal)
            except Exception as e:
                logger.error(
                    f"goals_repository.parse_error: goal_id={row.goal_id}, error={str(e)}"
                )
                continue

        return goals

    def _row_to_goal(self, row) -> Goal:
        """Convert database row to Goal model."""
        goal_data = dict(row.goal_data)

        # Add top-level fields from columns
        goal_data["goal_id"] = row.goal_id
        goal_data["user_id"] = row.user_id
        goal_data["version"] = row.version

        # Parse audit timestamps if they exist
        if not goal_data.get("audit"):
            goal_data["audit"] = {}

        goal_data["audit"]["created_at"] = row.created_at
        goal_data["audit"]["updated_at"] = row.updated_at

        return Goal(**goal_data)
