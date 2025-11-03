"""Info Nudge Evaluators - Individual evaluation logic for info-based nudge types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol
from uuid import UUID

from app.observability.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class EvaluatorConfig:
    nudge_id: str
    priority: int
    enabled: bool = True
    threshold: float = 0.5
    cooldown_hours: int = 24
    custom_params: Dict[str, Any] = None

    def __post_init__(self):
        if self.custom_params is None:
            self.custom_params = {}


class DataAccessLayer(Protocol):
    async def get_user_spending_trend(self, user_id: UUID, days: int = 30) -> Optional[Dict[str, Any]]:
        """Get user spending trends for the specified period."""
        ...

    async def get_user_goals(self, user_id: UUID) -> list[Dict[str, Any]]:
        """Get user financial goals."""
        ...

    async def get_budget_usage(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        """Get current budget usage for the user."""
        ...

    async def get_upcoming_subscriptions(self, user_id: UUID, days_ahead: int = 7) -> list[Dict[str, Any]]:
        """Get subscriptions due in the next N days."""
        ...

    async def get_failed_payments(self, user_id: UUID) -> list[Dict[str, Any]]:
        """Get recent failed payment attempts."""
        ...

    async def get_category_trends(self, user_id: UUID, days: int = 30) -> Dict[str, Any]:
        """Get spending trends by category."""
        ...


class InfoNudgeEvaluator(ABC):
    def __init__(self, config: EvaluatorConfig, data_access: Optional[DataAccessLayer] = None):
        self.config = config
        self.data_access = data_access
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    @property
    def nudge_id(self) -> str:
        return self.config.nudge_id

    @property
    def priority(self) -> int:
        return self.config.priority

    @abstractmethod
    async def evaluate_condition(self, user_id: UUID, context: Dict[str, Any]) -> bool:
        """Evaluate whether the nudge should be triggered.

        Args:
            user_id: The user to evaluate
            context: Additional context data (may include FOS-provided data)

        Returns:
            True if the nudge should be sent, False otherwise

        """
        pass

    @abstractmethod
    async def get_metadata(self, user_id: UUID, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate metadata to include with the nudge.

        Args:
            user_id: The user ID
            context: Evaluation context

        Returns:
            Dictionary with metadata specific to this nudge

        """
        pass

    async def should_send(self, user_id: UUID, context: Dict[str, Any]) -> bool:
        if not self.config.enabled:
            self.logger.debug(f"{self.nudge_id}.disabled: user_id={str(user_id)}")
            return False

        try:
            return await self.evaluate_condition(user_id, context)
        except Exception as e:
            self.logger.error(
                f"{self.nudge_id}.evaluation_error: user_id={str(user_id)}, error={str(e)}, error_type={type(e).__name__}"
            )
            return False


class SpendingAlertEvaluator(InfoNudgeEvaluator):
    async def evaluate_condition(self, user_id: UUID, context: Dict[str, Any]) -> bool:
        context.get("threshold", self.config.threshold)
        if self.data_access:
            # TODO: Replace with actual data fetching
            # trend_data = await self.data_access.get_user_spending_trend(user_id)
            # current_spending = trend_data.get("current_period_total", 0)
            # average_spending = trend_data.get("average_period_total", 0)
            # if average_spending > 0:
            #     increase_ratio = (current_spending - average_spending) / average_spending
            #     return increase_ratio > threshold
            pass
        self.logger.warning(f"{self.nudge_id}.not_implemented: user_id={str(user_id)}, using placeholder logic")
        return False

    async def get_metadata(self, user_id: UUID, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "evaluator": "spending_alert",
            "threshold_used": context.get("threshold", self.config.threshold),
            # TODO: Add actual spending data
            # "current_spending": current_spending,
            # "average_spending": average_spending,
            # "increase_percentage": increase_ratio * 100,
        }


class GoalMilestoneEvaluator(InfoNudgeEvaluator):
    async def evaluate_condition(self, user_id: UUID, context: Dict[str, Any]) -> bool:
        if self.data_access:
            # TODO: Implement goal milestone detection
            # goals = await self.data_access.get_user_goals(user_id)
            # for goal in goals:
            #     progress = goal.get("current_amount", 0) / goal.get("target_amount", 1)
            #     milestone_thresholds = [0.25, 0.50, 0.75, 1.0]
            #     if progress in milestone_thresholds:
            #         # Check if this milestone was already celebrated
            #         return True
            pass
        self.logger.warning(f"{self.nudge_id}.not_implemented: user_id={str(user_id)}, using placeholder logic")
        return False

    async def get_metadata(self, user_id: UUID, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "evaluator": "goal_milestone",
            # TODO: Add goal data
            # "goal_name": goal_name,
            # "progress_percentage": progress * 100,
            # "milestone_reached": milestone_percentage,
        }


class BudgetWarningEvaluator(InfoNudgeEvaluator):
    async def evaluate_condition(self, user_id: UUID, context: Dict[str, Any]) -> bool:
        context.get("warning_threshold", 0.8)
        if self.data_access:
            # TODO: Implement budget checking
            # budget_data = await self.data_access.get_budget_usage(user_id)
            # for category, data in budget_data.items():
            #     usage_ratio = data["spent"] / data["limit"]
            #     if usage_ratio >= warning_threshold:
            #         return True
            pass
        self.logger.warning(f"{self.nudge_id}.not_implemented: user_id={str(user_id)}, using placeholder logic")
        return False

    async def get_metadata(self, user_id: UUID, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "evaluator": "budget_warning",
            "warning_threshold": context.get("warning_threshold", 0.8),
            # TODO: Add budget data
            # "category": category_name,
            # "usage_percentage": usage_ratio * 100,
            # "amount_remaining": remaining_amount,
        }


class SubscriptionReminderEvaluator(InfoNudgeEvaluator):
    async def evaluate_condition(self, user_id: UUID, context: Dict[str, Any]) -> bool:
        context.get("days_ahead", 3)
        if self.data_access:
            # TODO: Implement subscription checking
            # subscriptions = await self.data_access.get_upcoming_subscriptions(user_id, days_ahead)
            # return len(subscriptions) > 0
            pass
        self.logger.warning(f"{self.nudge_id}.not_implemented: user_id={str(user_id)}, using placeholder logic")
        return False

    async def get_metadata(self, user_id: UUID, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "evaluator": "subscription_reminder",
            # TODO: Add subscription data
            # "subscription_name": sub_name,
            # "due_date": due_date.isoformat(),
            # "amount": amount,
        }


class SavingsOpportunityEvaluator(InfoNudgeEvaluator):
    async def evaluate_condition(self, user_id: UUID, context: Dict[str, Any]) -> bool:
        if self.data_access:
            # TODO: Implement savings opportunity detection
            # This is complex and may require ML models or heuristics
            # opportunities = await self._detect_savings_opportunities(user_id)
            # return len(opportunities) > 0
            pass
        self.logger.warning(f"{self.nudge_id}.not_implemented: user_id={str(user_id)}, using placeholder logic")
        return False

    async def get_metadata(self, user_id: UUID, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "evaluator": "savings_opportunity",
            # TODO: Add opportunity data
            # "opportunity_type": opp_type,
            # "potential_savings": estimated_savings,
        }


class PaymentFailedEvaluator(InfoNudgeEvaluator):
    async def evaluate_condition(self, user_id: UUID, context: Dict[str, Any]) -> bool:
        if self.data_access:
            # TODO: Implement failed payment checking
            # failed_payments = await self.data_access.get_failed_payments(user_id)
            # return len(failed_payments) > 0
            pass
        self.logger.warning(f"{self.nudge_id}.not_implemented: user_id={str(user_id)}, using placeholder logic")
        return False

    async def get_metadata(self, user_id: UUID, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "evaluator": "payment_failed",
            # TODO: Add payment failure data
            # "payment_description": payment_desc,
            # "amount": amount,
            # "failure_reason": reason,
        }


class CategoryInsightEvaluator(InfoNudgeEvaluator):
    async def evaluate_condition(self, user_id: UUID, context: Dict[str, Any]) -> bool:
        if self.data_access:
            # TODO: Implement category trend analysis
            # trends = await self.data_access.get_category_trends(user_id)
            # for category, trend in trends.items():
            #     if trend.get("change_percentage", 0) > 20:  # 20% change threshold
            #         return True
            pass
        self.logger.warning(f"{self.nudge_id}.not_implemented: user_id={str(user_id)}, using placeholder logic")
        return False

    async def get_metadata(self, user_id: UUID, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "evaluator": "category_insight",
            # TODO: Add category trend data
            # "category": category_name,
            # "trend": "increasing" or "decreasing",
            # "change_percentage": change_pct,
        }


class EvaluatorFactory:
    _evaluator_classes = {
        "spending_alert": SpendingAlertEvaluator,
        "goal_milestone": GoalMilestoneEvaluator,
        "budget_warning": BudgetWarningEvaluator,
        "subscription_reminder": SubscriptionReminderEvaluator,
        "savings_opportunity": SavingsOpportunityEvaluator,
        "payment_failed": PaymentFailedEvaluator,
        "category_insight": CategoryInsightEvaluator,
    }

    @classmethod
    def create_evaluator(
        cls,
        nudge_id: str,
        config: EvaluatorConfig,
        data_access: Optional[DataAccessLayer] = None,
    ) -> Optional[InfoNudgeEvaluator]:
        evaluator_class = cls._evaluator_classes.get(nudge_id)
        if not evaluator_class:
            logger.warning(
                f"evaluator_factory.unknown_type: nudge_id={nudge_id}, available={list(cls._evaluator_classes.keys())}"
            )
            return None

        return evaluator_class(config, data_access)

    @classmethod
    def register_evaluator_class(cls, nudge_id: str, evaluator_class: type[InfoNudgeEvaluator]):
        cls._evaluator_classes[nudge_id] = evaluator_class
        logger.info(f"evaluator_factory.custom_registered: nudge_id={nudge_id}, class={evaluator_class.__name__}")

    @classmethod
    def list_available_evaluators(cls) -> list[str]:
        return list(cls._evaluator_classes.keys())
