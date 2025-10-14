"""
Tests for info_strategy.py - Focus on BEHAVIOR not implementation.
"""
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.nudges.models import NudgeCandidate
from app.services.nudges.strategies.info_strategy import InfoNudgeStrategy


class TestNudgeEvaluationBehavior:

    @pytest.mark.asyncio
    @pytest.mark.parametrize("missing_field", ["nudge_id", "notification_text", "preview_text"])
    async def test_evaluation_fails_when_required_fields_missing(self, missing_field):
        strategy = InfoNudgeStrategy()
        user_id = uuid4()
        context = {"nudge_id": "spending_alert", "notification_text": "text", "preview_text": "preview"}
        del context[missing_field]
        result = await strategy.evaluate(user_id, context)
        assert result is None

    @pytest.mark.asyncio
    async def test_evaluation_fails_for_unregistered_nudge_types(self):
        strategy = InfoNudgeStrategy()
        user_id = uuid4()
        context = {"nudge_id": "unknown_type", "notification_text": "text", "preview_text": "preview"}
        result = await strategy.evaluate(user_id, context)
        assert result is None

    @pytest.mark.asyncio
    async def test_evaluation_respects_evaluator_decision(self):
        strategy = InfoNudgeStrategy()
        user_id = uuid4()
        context = {"nudge_id": "spending_alert", "notification_text": "text", "preview_text": "preview"}
        mock_eval = AsyncMock(return_value=False)
        strategy.evaluators["spending_alert"] = mock_eval
        result = await strategy.evaluate(user_id, context)
        assert result is None
        mock_eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluation_creates_nudge_when_all_conditions_met(self):
        strategy = InfoNudgeStrategy()
        user_id = uuid4()
        context = {"nudge_id": "payment_failed", "notification_text": "Payment failed", "preview_text": "Update payment", "metadata": {"tx_id": "123"}}
        mock_eval = AsyncMock(return_value=True)
        strategy.evaluators["payment_failed"] = mock_eval
        result = await strategy.evaluate(user_id, context)
        assert isinstance(result, NudgeCandidate)
        assert result.notification_text == "Payment failed"
        assert result.metadata["nudge_id"] == "payment_failed"

    @pytest.mark.asyncio
    async def test_evaluation_handles_evaluator_exceptions_gracefully(self):
        strategy = InfoNudgeStrategy()
        user_id = uuid4()
        context = {"nudge_id": "spending_alert", "notification_text": "text", "preview_text": "preview"}
        mock_eval = AsyncMock(side_effect=Exception("DB error"))
        strategy.evaluators["spending_alert"] = mock_eval
        result = await strategy.evaluate(user_id, context)
        assert result is None

    @pytest.mark.asyncio
    async def test_evaluation_handles_missing_optional_metadata(self):
        strategy = InfoNudgeStrategy()
        user_id = uuid4()
        context = {"nudge_id": "goal_milestone", "notification_text": "Goal reached", "preview_text": "Great"}
        mock_eval = AsyncMock(return_value=True)
        strategy.evaluators["goal_milestone"] = mock_eval
        result = await strategy.evaluate(user_id, context)
        assert isinstance(result, NudgeCandidate)
        assert result.metadata["evaluation_context"] == {}


class TestCustomEvaluatorIntegration:

    @pytest.mark.asyncio
    async def test_custom_evaluator_works_end_to_end(self):
        strategy = InfoNudgeStrategy()
        user_id = uuid4()
        async def custom_eval(uid, ctx):
            return ctx.get("fraud_detected", False)
        strategy.register_evaluator("fraud_alert", custom_eval, priority=5)
        context = {"nudge_id": "fraud_alert", "notification_text": "Fraud detected", "preview_text": "Review", "fraud_detected": True}
        result = await strategy.evaluate(user_id, context)
        assert isinstance(result, NudgeCandidate)
        assert result.priority == 5
