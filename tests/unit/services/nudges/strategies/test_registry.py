import threading
from typing import Any, Dict, Optional
from unittest.mock import patch
from uuid import UUID

from app.services.nudges.models import NudgeCandidate
from app.services.nudges.strategies.base import NudgeStrategy
from app.services.nudges.strategies.bill_strategy import BillNudgeStrategy
from app.services.nudges.strategies.info_strategy import InfoNudgeStrategy
from app.services.nudges.strategies.memory_strategy import MemoryNudgeStrategy
from app.services.nudges.strategies.registry import StrategyRegistry, get_strategy_registry


class MockStrategy(NudgeStrategy):
    def __init__(self):
        self._nudge_type = "mock_type"
        self._requires_fos = False

    @property
    def nudge_type(self) -> str:
        return self._nudge_type

    @property
    def requires_fos_text(self) -> bool:
        return self._requires_fos

    async def evaluate(self, user_id: UUID, context: Dict[str, Any]) -> Optional[NudgeCandidate]:
        return None

    def get_priority(self, context: Dict[str, Any]) -> int:
        return 3


class FailingStrategy(NudgeStrategy):
    def __init__(self):
        raise RuntimeError("Fail")

    @property
    def nudge_type(self) -> str:
        return "fail"

    @property
    def requires_fos_text(self) -> bool:
        return False

    async def evaluate(self, user_id: UUID, context: Dict[str, Any]) -> Optional[NudgeCandidate]:
        return None

    def get_priority(self, context: Dict[str, Any]) -> int:
        return 1


class TestStrategyRegistry:
    def test_initialization_and_defaults(self):
        registry = StrategyRegistry()

        assert registry._strategies == {}
        assert hasattr(registry, '_lock')
        assert len(registry._strategy_classes) == 4
        assert registry._strategy_classes["static_bill"] == BillNudgeStrategy
        assert registry._strategy_classes["memory_icebreaker"] == MemoryNudgeStrategy
        assert registry._strategy_classes["info_based"] == InfoNudgeStrategy

    def test_register_and_get_strategy_class(self):
        registry = StrategyRegistry()
        registry.register_strategy_class("custom", MockStrategy)

        assert "custom" in registry._strategy_classes
        strategy = registry.get_strategy("custom")
        assert isinstance(strategy, MockStrategy)
        assert strategy is registry.get_strategy("custom")

    def test_get_strategy_unknown_returns_none(self):
        registry = StrategyRegistry()
        assert registry.get_strategy("unknown") is None
        assert registry.get_strategy(None) is None
        assert registry.get_strategy("") is None

    def test_get_strategy_instantiation_failure(self):
        registry = StrategyRegistry()
        registry.register_strategy_class("fail", FailingStrategy)
        assert registry.get_strategy("fail") is None

    def test_register_and_get_custom_strategy_instance(self):
        registry = StrategyRegistry()
        mock = MockStrategy()

        registry.register_custom_strategy(mock)
        assert registry.get_strategy("mock_type") is mock

    def test_list_available_strategies(self):
        registry = StrategyRegistry()
        registry.register_strategy_class("custom", MockStrategy)

        available = registry.list_available_strategies()
        assert isinstance(available, list)
        assert "static_bill" in available
        assert "memory_icebreaker" in available
        assert "info_based" in available
        assert "custom" in available

    def test_is_fos_controlled(self):
        registry = StrategyRegistry()

        assert registry.is_fos_controlled("info_based") is True
        assert registry.is_fos_controlled("static_bill") is False
        assert registry.is_fos_controlled("unknown") is False

    def test_singleton_pattern(self):
        registry1 = get_strategy_registry()
        registry2 = get_strategy_registry()

        assert registry1 is registry2
        assert isinstance(registry1, StrategyRegistry)
        assert len(registry1.list_available_strategies()) >= 3

    def test_thread_safety(self):
        registry = StrategyRegistry()
        results = []

        def get_and_store():
            strategy = registry.get_strategy("static_bill")
            results.append(id(strategy))

        threads = [threading.Thread(target=get_and_store) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(set(results)) == 1
        assert len(results) == 20

    def test_logging(self):
        with patch('app.services.nudges.strategies.registry.logger') as mock_logger:
            registry = StrategyRegistry()
            registry.register_strategy_class("test", MockStrategy)
            registry.register_custom_strategy(MockStrategy())
            registry.get_strategy("test")
            registry.get_strategy("unknown")

            assert mock_logger.info.call_count >= 3
            assert mock_logger.warning.call_count >= 1
