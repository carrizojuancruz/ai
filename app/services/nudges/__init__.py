"""Nudges Service Module - handles nudge evaluation, queueing, and management."""

from .activity_counter import ActivityCounter, get_activity_counter
from .bill_detector import BillDetector, get_bill_detector
from .evaluator import NudgeEvaluator, get_nudge_evaluator, iter_active_users
from .selector import NudgeSelector
from .templates import NudgeRegistry, NudgeTemplate

__all__ = [
    "ActivityCounter",
    "BillDetector",
    "NudgeEvaluator",
    "NudgeSelector",
    "NudgeTemplate",
    "NudgeRegistry",
    "get_activity_counter",
    "get_bill_detector",
    "get_nudge_evaluator",
    "iter_active_users",
]
