from typing import Any, Dict, Optional
from uuid import UUID

from app.observability.logging_config import get_logger
from app.services.nudges.models import NudgeCandidate
from app.services.nudges.strategies.base import NudgeStrategy
from app.services.nudges.strategies.info_evaluators import (
    DataAccessLayer,
    EvaluatorConfig,
    EvaluatorFactory,
    InfoNudgeEvaluator,
)

logger = get_logger(__name__)


class InfoNudgeStrategy(NudgeStrategy):
    """Strategy for info-based nudges."""

    def __init__(self, data_access: Optional[DataAccessLayer] = None):
        self.data_access = data_access
        self.evaluators: Dict[str, InfoNudgeEvaluator] = {}
        self._initialize_default_evaluators()

    def _initialize_default_evaluators(self):
        default_configs = {
            "payment_failed": EvaluatorConfig(nudge_id="payment_failed", priority=5, threshold=0.95),
            "spending_alert": EvaluatorConfig(nudge_id="spending_alert", priority=4, threshold=0.7),
            "goal_milestone": EvaluatorConfig(nudge_id="goal_milestone", priority=3, threshold=0.8),
            "budget_warning": EvaluatorConfig(nudge_id="budget_warning", priority=3, threshold=0.75),
            "category_insight": EvaluatorConfig(nudge_id="category_insight", priority=2, threshold=0.8),
            "subscription_reminder": EvaluatorConfig(nudge_id="subscription_reminder", priority=2, threshold=0.85),
            "savings_opportunity": EvaluatorConfig(nudge_id="savings_opportunity", priority=1, threshold=0.9),
        }
        for nudge_id, config in default_configs.items():
            evaluator = EvaluatorFactory.create_evaluator(nudge_id, config, self.data_access)
            if evaluator:
                self.evaluators[nudge_id] = evaluator
                logger.debug(f"info_strategy.evaluator_initialized: nudge_id={nudge_id}, priority={config.priority}")
        logger.info(f"info_strategy.initialized: evaluator_count={len(self.evaluators)}")

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

            should_send = await evaluator.should_send(user_id, context)
            if not should_send:
                logger.debug(f"info_strategy.condition_not_met: user_id={str(user_id)}, nudge_id={nudge_id}")
                return None

            evaluator_metadata = await evaluator.get_metadata(user_id, context)
            priority = evaluator.priority

            candidate = NudgeCandidate(
                user_id=user_id,
                nudge_type=self.nudge_type,
                priority=priority,
                notification_text=notification_text,
                preview_text=preview_text,
                metadata={
                    "nudge_id": nudge_id,
                    "fos_controlled": True,
                    "evaluation_context": context.get("metadata", {}),
                    "evaluator_metadata": evaluator_metadata,
                },
            )

            logger.info(
                f"info_strategy.candidate_created: user_id={str(user_id)}, nudge_id={nudge_id}, priority={priority}"
            )
            return candidate

        except Exception as e:
            logger.error(
                f"info_strategy.evaluation_failed: user_id={str(user_id)}, nudge_id={context.get('nudge_id')}, error={str(e)}, error_type={type(e).__name__}"
            )
            return None

    def get_priority(self, context: Dict[str, Any]) -> int:
        nudge_id = context.get("nudge_id")
        evaluator = self.evaluators.get(nudge_id)
        if evaluator:
            return evaluator.priority
        return 2

    def register_custom_evaluator(self, evaluator: InfoNudgeEvaluator):
        nudge_id = evaluator.nudge_id
        self.evaluators[nudge_id] = evaluator
        logger.info(
            f"info_strategy.custom_evaluator_registered: nudge_id={nudge_id}, priority={evaluator.priority}, class={evaluator.__class__.__name__}"
        )

    def get_evaluator_config(self, nudge_id: str) -> Optional[EvaluatorConfig]:
        evaluator = self.evaluators.get(nudge_id)
        if evaluator:
            return evaluator.config
        return None

    def update_evaluator_config(self, nudge_id: str, **config_updates):
        evaluator = self.evaluators.get(nudge_id)
        if not evaluator:
            logger.warning(f"info_strategy.update_config_failed: nudge_id={nudge_id} not found")
            return

        for key, value in config_updates.items():
            if hasattr(evaluator.config, key):
                setattr(evaluator.config, key, value)
                logger.info(f"info_strategy.config_updated: nudge_id={nudge_id}, {key}={value}")
            else:
                logger.warning(f"info_strategy.invalid_config_key: nudge_id={nudge_id}, key={key}")

    def list_available_nudges(self) -> list[str]:
        return list(self.evaluators.keys())
