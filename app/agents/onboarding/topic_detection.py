from __future__ import annotations

from typing import Any, Protocol

from .constants import KEYWORDS_BY_NODE
from .state import OnboardingStep


class TopicDetectionStrategy(Protocol):
    def should_show(self, node: OnboardingStep, state: Any) -> bool: ...


class KeywordTopicDetection:
    def should_show(self, node: OnboardingStep, state: Any) -> bool:
        keywords = KEYWORDS_BY_NODE.get(node) or []
        if not keywords:
            return False
        return state.has_mentioned_topic(keywords)


_strategy: TopicDetectionStrategy = KeywordTopicDetection()


def set_topic_detection_strategy(strategy: TopicDetectionStrategy) -> None:
    global _strategy
    _strategy = strategy


def get_topic_detection_strategy() -> TopicDetectionStrategy:
    return _strategy
