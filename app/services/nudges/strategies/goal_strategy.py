from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.agents.supervisor.goal_agent.models import Goal
from app.observability.logging_config import get_logger
from app.repositories.database_service import get_database_service
from app.repositories.postgres.goals_repository import GoalsRepository
from app.services.nudges.models import NudgeCandidate
from app.services.nudges.strategies.base import NudgeStrategy

logger = get_logger(__name__)


class GoalNudgeStrategy(NudgeStrategy):
    """Self-Service strategy for goal-based nudges.

    Follows the same pattern as PlaidBillsService - queries DB directly,
    filters goals, and generates notifications.
    """

    def __init__(self):
        self.db_service = get_database_service()
        self.priority_map = {
            "goal_completed": 5,
            "goal_near_deadline": 4,
            "goal_high_progress": 3,
            "goal_pending": 2,
        }

    @property
    def nudge_type(self) -> str:
        return "goal_based"

    @property
    def requires_fos_text(self) -> bool:
        return False  # Self-service generates its own text

    async def evaluate(self, user_id: UUID, context: Dict[str, Any]) -> Optional[NudgeCandidate]:
        """Evaluate user's goals and return highest priority nudge candidate."""
        try:
            # Fetch user's active goals from DB
            goals = await self._get_user_goals(user_id)

            if not goals:
                logger.debug(f"goal_strategy.no_goals: user_id={str(user_id)}")
                return None

            logger.info(f"goal_strategy.fetched_goals: user_id={str(user_id)}, count={len(goals)}")

            # Filter goals that need nudges
            filtered_goals = self._filter_goals_needing_nudge(goals)

            if not filtered_goals:
                logger.debug(
                    f"goal_strategy.no_goals_need_nudge: user_id={str(user_id)}, total_goals={len(goals)}"
                )
                return None

            # Get highest priority goal
            best_goal = self._select_highest_priority_goal(filtered_goals)

            # Determine nudge reason
            should_send, nudge_id = self._evaluate_goal_conditions(best_goal)

            if not should_send:
                return None

            # Generate notification texts
            notification_text = self._generate_notification_text(best_goal, nudge_id)
            preview_text = self._generate_preview_text(best_goal, nudge_id)

            priority = self.priority_map.get(nudge_id, 2)

            logger.info(
                f"goal_strategy.candidate_created: user_id={str(user_id)}, "
                f"goal_id={str(best_goal.goal_id)}, nudge_id={nudge_id}, priority={priority}"
            )

            return NudgeCandidate(
                user_id=user_id,
                nudge_type=self.nudge_type,
                priority=priority,
                notification_text=notification_text,
                preview_text=preview_text,
                metadata={
                    "nudge_id": nudge_id,
                    "goal_id": str(best_goal.goal_id),
                    "status": best_goal.status.value,
                    "percent_complete": float(best_goal.progress.percent_complete),
                    "goal_title": best_goal.goal.title,
                },
            )

        except Exception as e:
            logger.error(f"goal_strategy.evaluation_failed: user_id={str(user_id)}, error={str(e)}")
            return None

    async def _get_user_goals(self, user_id: UUID) -> List[Goal]:
        """Fetch active goals from database."""
        async with self.db_service.get_session() as session:
            repo = GoalsRepository(session)
            return await repo.get_goals_by_user(user_id, is_active=True)

    def _filter_goals_needing_nudge(self, goals: List[Goal]) -> List[Goal]:
        """Filter goals that meet nudge criteria."""
        filtered = []
        now = datetime.now()

        for goal in goals:
            if not goal.notifications_enabled:
                continue

            should_notify = (
                # Completed with end date
                (goal.status.value == "completed" and goal.end_date is not None and not goal.no_end_date)
                # High progress
                or (goal.status.value == "in_progress" and goal.progress.percent_complete >= 75)
                # Pending
                or goal.status.value == "pending"
                # Deadline approaching
                or (goal.end_date is not None and 0 <= (goal.end_date - now).days <= 7)
            )

            if should_notify:
                filtered.append(goal)

        return filtered

    def _select_highest_priority_goal(self, goals: List[Goal]) -> Goal:
        """Select goal with highest priority nudge."""
        # Sort by: completed > near_deadline > high_progress > pending
        def priority_score(g: Goal):
            if g.status.value == "completed":
                return 5
            if g.end_date and (g.end_date - datetime.now()).days <= 7:
                return 4
            if g.status.value == "in_progress" and g.progress.percent_complete >= 75:
                return 3
            if g.status.value == "pending":
                return 2
            return 1

        return max(goals, key=priority_score)

    def _evaluate_goal_conditions(self, goal: Goal) -> tuple[bool, str]:
        """Determine nudge type for goal."""
        # 1. Completed
        if goal.status.value == "completed" and goal.end_date is not None and not goal.no_end_date:
            return True, "goal_completed"

        # 2. High progress
        if goal.status.value == "in_progress" and goal.progress.percent_complete >= 75:
            return True, "goal_high_progress"

        # 3. Pending
        if goal.status.value == "pending":
            return True, "goal_pending"

        # 4. Deadline approaching
        if goal.end_date:
            days_until = (goal.end_date - datetime.now()).days
            if days_until == 7:
                return True, "goal_near_deadline"

        return False, ""

    def _generate_notification_text(self, goal: Goal, nudge_id: str) -> str:
        """Generate notification text."""
        title = goal.goal.title

        templates = {
            "goal_completed": f"🎉 Congratulations! You've completed your goal: '{title}'",
            "goal_high_progress": f"🚀 You're almost there! Your goal '{title}' is {goal.progress.percent_complete:.0f}% complete",
            "goal_pending": f"💪 Ready to start your goal '{title}'?",
            "goal_near_deadline": f"⏰ Only 7 days left to complete your goal: '{title}'",
        }

        return templates.get(nudge_id, f"Update on your goal: '{title}'")

    def _generate_preview_text(self, goal: Goal, nudge_id: str) -> str:
        """Generate preview text."""
        previews = {
            "goal_completed": "Goal completed!",
            "goal_high_progress": f"{goal.progress.percent_complete:.0f}% complete",
            "goal_pending": "Ready to start?",
            "goal_near_deadline": "Deadline approaching",
        }

        return previews.get(nudge_id, "Goal update")

    def get_priority(self, context: Dict[str, Any]) -> int:
        nudge_id = context.get("nudge_id")
        return self.priority_map.get(nudge_id, 2)
