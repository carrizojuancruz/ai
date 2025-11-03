"""Goals service for business logic and nudge orchestration."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from app.agents.supervisor.goal_agent.models import Goal
from app.observability.logging_config import get_logger
from app.repositories.database_service import get_database_service
from app.repositories.postgres.goals_repository import GoalsRepository
from app.services.nudges.evaluator import get_nudge_evaluator

logger = get_logger(__name__)


class GoalsService:
    """Service for managing goals and triggering notifications."""

    def __init__(self):
        self.db_service = get_database_service()
        self.nudge_evaluator = get_nudge_evaluator()

    async def get_goal(self, goal_id: UUID) -> Optional[Goal]:
        """Get a single goal by ID."""
        async with self.db_service.get_session() as session:
            repo = GoalsRepository(session)
            return await repo.get_goal_by_id(goal_id)

    async def get_user_goals(self, user_id: UUID, is_active: bool = True) -> List[Goal]:
        """Get all goals for a user."""
        async with self.db_service.get_session() as session:
            repo = GoalsRepository(session)
            return await repo.get_goals_by_user(user_id, is_active)

    async def check_and_trigger_nudge(self, goal: Goal) -> Optional[dict]:
        """Check if goal needs nudge and trigger it."""
        if not goal.notifications_enabled:
            logger.debug(
                f"goals_service.notifications_disabled: goal_id={str(goal.goal_id)}, user_id={str(goal.user_id)}"
            )
            return None

        # Check if goal meets any nudge criteria
        should_notify, nudge_reason = self._should_notify(goal)

        if not should_notify:
            logger.debug(
                f"goals_service.no_nudge_needed: goal_id={str(goal.goal_id)}, status={goal.status.value}, percent={goal.progress.percent_complete}"
            )
            return None

        logger.info(
            f"goals_service.triggering_nudge: goal_id={str(goal.goal_id)}, reason={nudge_reason}, status={goal.status.value}"
        )

        # Generate notification texts
        notification_text = self._generate_notification_text(goal, nudge_reason)
        preview_text = self._generate_preview_text(goal, nudge_reason)

        # Trigger nudge evaluation
        result = await self.nudge_evaluator.evaluate_nudges_batch(
            user_ids=[str(goal.user_id)],
            nudge_type="goal_based",
            # Context completo del goal
            goal_id=str(goal.goal_id),
            notifications_enabled=goal.notifications_enabled,
            notification_text=notification_text,
            preview_text=preview_text,
            status=goal.status.value,
            percent_complete=float(goal.progress.percent_complete),
            end_date=goal.end_date.isoformat() if goal.end_date else None,
            no_end_date=goal.no_end_date,
            metadata={
                "goal_title": goal.goal.title,
                "goal_category": goal.category.value,
                "nudge_reason": nudge_reason,
            },
        )

        logger.info(
            f"goals_service.nudge_triggered: goal_id={str(goal.goal_id)}, result={result}"
        )

        return result

    async def check_all_goals_for_nudges(self, days_ahead: int = 7) -> dict:
        """Check all goals that might need notifications (for cron job).

        Fetches ALL active goals with notifications enabled, then filters in Python.
        """
        async with self.db_service.get_session() as session:
            repo = GoalsRepository(session)
            all_goals = await repo.get_active_goals_with_notifications()

        logger.info(f"goals_service.fetched_goals: total_count={len(all_goals)}")

        # Filter goals in Python code
        filtered_goals = self._filter_goals_needing_nudge(all_goals, days_ahead)

        logger.info(
            f"goals_service.filtered_goals: total={len(all_goals)}, "
            f"need_nudge={len(filtered_goals)}"
        )

        triggered = 0
        skipped = 0

        for goal in filtered_goals:
            try:
                result = await self.check_and_trigger_nudge(goal)
                if result:
                    triggered += 1
                else:
                    skipped += 1
            except Exception as e:
                logger.error(
                    f"goals_service.nudge_check_failed: goal_id={str(goal.goal_id)}, error={str(e)}"
                )
                skipped += 1

        logger.info(
            f"goals_service.batch_complete: total={len(all_goals)}, "
            f"filtered={len(filtered_goals)}, triggered={triggered}, skipped={skipped}"
        )

        return {
            "total_goals": len(all_goals),
            "filtered": len(filtered_goals),
            "triggered": triggered,
            "skipped": skipped,
        }

    def _filter_goals_needing_nudge(
        self, goals: List[Goal], days_ahead: int = 7
    ) -> List[Goal]:
        """Filter goals that need nudge notifications.

        Pre-processes all goals and returns only those meeting nudge criteria.
        """
        filtered = []
        now = datetime.now()

        for goal in goals:
            # Skip if notifications disabled (double-check)
            if not goal.notifications_enabled:
                continue

            # Check if goal meets any nudge criteria
            should_notify = (
                # 1. Completed goal with end date
                (
                    goal.status.value == "completed"
                    and goal.end_date is not None
                    and not goal.no_end_date
                )
                # 2. High progress (>= 75%)
                or (
                    goal.status.value == "in_progress"
                    and goal.progress.percent_complete >= 75
                )
                # 3. Pending goal
                or goal.status.value == "pending"
                # 4. Deadline approaching (within days_ahead window)
                or (
                    goal.end_date is not None
                    and 0 <= (goal.end_date - now).days <= days_ahead
                )
            )

            if should_notify:
                filtered.append(goal)
                logger.debug(
                    f"goals_service.goal_needs_nudge: goal_id={str(goal.goal_id)}, "
                    f"status={goal.status.value}, progress={goal.progress.percent_complete}"
                )

        return filtered

    def _should_notify(self, goal: Goal) -> tuple[bool, str]:
        """Determine if goal should trigger notification and return reason."""
        # 1. Completed goal with end date
        if (
            goal.status.value == "completed"
            and goal.end_date is not None
            and not goal.no_end_date
        ):
            return True, "goal_completed"

        # 2. High progress (>= 75%)
        if (
            goal.status.value == "in_progress"
            and goal.progress.percent_complete >= 75
        ):
            return True, "goal_high_progress"

        # 3. Pending goal
        if goal.status.value == "pending":
            return True, "goal_pending"

        # 4. Deadline approaching (7 days)
        if goal.end_date:
            days_until = (goal.end_date - datetime.now()).days
            if days_until == 7:
                return True, "goal_near_deadline"

        return False, ""

    def _generate_notification_text(self, goal: Goal, reason: str) -> str:
        """Generate notification text based on goal and reason."""
        title = goal.goal.title

        templates = {
            "goal_completed": f"🎉 Congratulations! You've completed your goal: '{title}'",
            "goal_high_progress": f"🚀 You're almost there! Your goal '{title}' is {goal.progress.percent_complete:.0f}% complete",
            "goal_pending": f"💪 Ready to start your goal '{title}'?",
            "goal_near_deadline": f"⏰ Only 7 days left to complete your goal: '{title}'",
        }

        return templates.get(reason, f"Update on your goal: '{title}'")

    def _generate_preview_text(self, goal: Goal, reason: str) -> str:
        """Generate preview text based on goal and reason."""
        previews = {
            "goal_completed": "Goal completed!",
            "goal_high_progress": f"{goal.progress.percent_complete:.0f}% complete",
            "goal_pending": "Ready to start?",
            "goal_near_deadline": "Deadline approaching",
        }

        return previews.get(reason, "Goal update")


# Singleton instance
_goals_service: Optional[GoalsService] = None


def get_goals_service() -> GoalsService:
    """Get or create goals service singleton."""
    global _goals_service
    if _goals_service is None:
        _goals_service = GoalsService()
    return _goals_service
