import threading
from typing import Dict, Optional, Type

from app.observability.logging_config import get_logger
from app.services.nudges.strategies.base import NudgeStrategy
from app.services.nudges.strategies.bill_strategy import BillNudgeStrategy
from app.services.nudges.strategies.info_strategy import InfoNudgeStrategy
from app.services.nudges.strategies.memory_strategy import MemoryNudgeStrategy

logger = get_logger(__name__)


class StrategyRegistry:
    def __init__(self):
        self._strategies: Dict[str, NudgeStrategy] = {}
        self._strategy_classes: Dict[str, Type[NudgeStrategy]] = {}
        self._lock = threading.RLock()
        self._register_defaults()

    def _register_defaults(self):
        self.register_strategy_class("static_bill", BillNudgeStrategy)
        self.register_strategy_class("memory_icebreaker", MemoryNudgeStrategy)
        self.register_strategy_class("info_based", InfoNudgeStrategy)
        logger.info(f"strategy_registry.defaults_registered: strategies={list(self._strategy_classes.keys())}")

    def register_strategy_class(self, nudge_type: str, strategy_class: Type[NudgeStrategy]):
        self._strategy_classes[nudge_type] = strategy_class
        logger.info(
            f"strategy_registry.class_registered: nudge_type={nudge_type}, strategy_class={strategy_class.__name__}"
        )

    def get_strategy(self, nudge_type: str) -> Optional[NudgeStrategy]:
        with self._lock:
            if nudge_type in self._strategies:
                return self._strategies[nudge_type]

            strategy_class = self._strategy_classes.get(nudge_type)
            if not strategy_class:
                logger.warning(
                    f"strategy_registry.unknown_type: nudge_type={nudge_type}, available_types={list(self._strategy_classes.keys())}"
                )
                return None

            try:
                strategy = strategy_class()
                self._strategies[nudge_type] = strategy
                logger.info(
                    f"strategy_registry.strategy_created: nudge_type={nudge_type}, strategy_class={strategy_class.__name__}"
                )
                return strategy
            except Exception as e:
                logger.error(
                    f"strategy_registry.instantiation_failed: nudge_type={nudge_type}, strategy_class={strategy_class.__name__}, error={str(e)}"
                )
                return None

    def register_custom_strategy(self, strategy: NudgeStrategy):
        with self._lock:
            nudge_type = strategy.nudge_type
            self._strategies[nudge_type] = strategy
            logger.info(
                f"strategy_registry.custom_registered: nudge_type={nudge_type}, strategy_class={strategy.__class__.__name__}"
            )

    def list_available_strategies(self) -> list[str]:
        return list(self._strategy_classes.keys())

    def is_fos_controlled(self, nudge_type: str) -> bool:
        strategy = self.get_strategy(nudge_type)
        if not strategy:
            return False
        return strategy.requires_fos_text


_strategy_registry = None


def get_strategy_registry() -> StrategyRegistry:
    global _strategy_registry
    if _strategy_registry is None:
        _strategy_registry = StrategyRegistry()
    return _strategy_registry
