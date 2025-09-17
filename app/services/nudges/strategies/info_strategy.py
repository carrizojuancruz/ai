import random
from typing import Any, Callable, Dict, Optional
from uuid import UUID

from app.observability.logging_config import get_logger
from app.services.nudges.models import NudgeCandidate
from app.services.nudges.strategies.base import NudgeStrategy

logger = get_logger(__name__)


class InfoNudgeStrategy(NudgeStrategy):
    def __init__(self):
        self.evaluators: Dict[str, Callable] = {
            "spending_alert": self._check_spending_increase,
            "goal_milestone": self._check_goal_progress,
            "budget_warning": self._check_budget_usage,
            "subscription_reminder": self._check_upcoming_subscription,
            "savings_opportunity": self._check_savings_potential,
            "payment_failed": self._check_failed_payment,
            "category_insight": self._check_category_trend,
        }

        self.priority_map = {
            "payment_failed": 5,
            "spending_alert": 4,
            "goal_milestone": 3,
            "budget_warning": 3,
            "category_insight": 2,
            "subscription_reminder": 2,
            "savings_opportunity": 1,
        }

    @property
    def nudge_type(self) -> str:
        return "info_based"

    @property
    def requires_fos_text(self) -> bool:
        return True

    async def evaluate(self, user_id: UUID, context: Dict[str, Any]) -> Optional[NudgeCandidate]:
        try:
            nudge_id = context.get("nudge_id")
            notification_text = context.get("notification_text")
            preview_text = context.get("preview_text")

            if not all([nudge_id, notification_text, preview_text]):
                logger.warning(
                    f"info_strategy.missing_required_fields: user_id={str(user_id)}, nudge_id={nudge_id}, has_text={bool(notification_text)}, has_preview={bool(preview_text)}"
                )
                return None

            evaluator = self.evaluators.get(nudge_id)
            if not evaluator:
                logger.warning(
                    f"info_strategy.unknown_nudge_id: nudge_id={nudge_id}, user_id={str(user_id)}, available_ids={list(self.evaluators.keys())}"
                )
                return None

            should_send = await evaluator(user_id, context)

            if not should_send:
                logger.debug(f"info_strategy.condition_not_met: user_id={str(user_id)}, nudge_id={nudge_id}")
                return None

            priority = self.get_priority({"nudge_id": nudge_id})

            return NudgeCandidate(
                user_id=user_id,
                nudge_type=self.nudge_type,
                priority=priority,
                notification_text=notification_text,
                preview_text=preview_text,
                metadata={
                    "nudge_id": nudge_id,
                    "fos_controlled": True,
                    "evaluation_context": context.get("metadata", {}),
                },
            )

        except Exception as e:
            logger.error(
                f"info_strategy.evaluation_failed: user_id={str(user_id)}, nudge_id={context.get('nudge_id')}, error={str(e)}"
            )
            return None

    def get_priority(self, context: Dict[str, Any]) -> int:
        nudge_id = context.get("nudge_id")
        return self.priority_map.get(nudge_id, 2)

    async def _check_spending_increase(self, user_id: UUID, context: Dict[str, Any]) -> bool:
        threshold = context.get("threshold", 0.7)
        return random.random() > threshold

    async def _check_goal_progress(self, user_id: UUID, context: Dict[str, Any]) -> bool:
        return random.random() > 0.8

    async def _check_budget_usage(self, user_id: UUID, context: Dict[str, Any]) -> bool:
        return random.random() > 0.75

    async def _check_upcoming_subscription(self, user_id: UUID, context: Dict[str, Any]) -> bool:
        return random.random() > 0.85

    async def _check_savings_potential(self, user_id: UUID, context: Dict[str, Any]) -> bool:
        return random.random() > 0.9

    async def _check_failed_payment(self, user_id: UUID, context: Dict[str, Any]) -> bool:
        return random.random() > 0.95

    async def _check_category_trend(self, user_id: UUID, context: Dict[str, Any]) -> bool:
        return random.random() > 0.8

    def register_evaluator(self, nudge_id: str, evaluator: Callable, priority: int = 2):
        self.evaluators[nudge_id] = evaluator
        self.priority_map[nudge_id] = priority

        logger.info(f"info_strategy.evaluator_registered: nudge_id={nudge_id}, priority={priority}")
