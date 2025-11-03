"""
Behavioral tests for info_strategy.py.
"""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.nudges.models import NudgeCandidate
from app.services.nudges.strategies.info_evaluators import EvaluatorConfig, InfoNudgeEvaluator
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
        mock_eval = MagicMock()
        mock_eval.should_send = AsyncMock(return_value=False)
        mock_eval.priority = 4
        mock_eval.nudge_id = "spending_alert"
        strategy.evaluators["spending_alert"] = mock_eval
        result = await strategy.evaluate(user_id, context)
        assert result is None
        mock_eval.should_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluation_creates_nudge_when_all_conditions_met(self):
        strategy = InfoNudgeStrategy()
        user_id = uuid4()
        context = {
            "nudge_id": "payment_failed",
            "notification_text": "Payment failed",
            "preview_text": "Update payment",
            "metadata": {"tx_id": "123"},
        }
        mock_eval = MagicMock()
        mock_eval.should_send = AsyncMock(return_value=True)
        mock_eval.get_metadata = AsyncMock(return_value={"evaluator": "payment_failed"})
        mock_eval.priority = 5
        mock_eval.nudge_id = "payment_failed"
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
        mock_eval = MagicMock()
        mock_eval.should_send = AsyncMock(side_effect=Exception("DB error"))
        mock_eval.priority = 4
        mock_eval.nudge_id = "spending_alert"
        strategy.evaluators["spending_alert"] = mock_eval
        result = await strategy.evaluate(user_id, context)
        assert result is None

    @pytest.mark.asyncio
    async def test_evaluation_handles_missing_optional_metadata(self):
        strategy = InfoNudgeStrategy()
        user_id = uuid4()
        context = {
            "nudge_id": "goal_milestone",
            "notification_text": "Goal reached",
            "preview_text": "Great",
        }
        mock_eval = MagicMock()
        mock_eval.should_send = AsyncMock(return_value=True)
        mock_eval.get_metadata = AsyncMock(return_value={"evaluator": "goal_milestone"})
        mock_eval.priority = 3
        mock_eval.nudge_id = "goal_milestone"
        strategy.evaluators["goal_milestone"] = mock_eval
        result = await strategy.evaluate(user_id, context)
        assert isinstance(result, NudgeCandidate)
        assert result.metadata["evaluation_context"] == {}


class TestCustomEvaluatorIntegration:
    @pytest.mark.asyncio
    async def test_custom_evaluator_works_end_to_end(self):
        class FraudAlertEvaluator(InfoNudgeEvaluator):
            async def evaluate_condition(self, user_id, context):
                return context.get("fraud_detected", False)

            async def get_metadata(self, user_id, context):
                return {"evaluator": "fraud_alert", "fraud_detected": context.get("fraud_detected")}

        strategy = InfoNudgeStrategy()
        user_id = uuid4()
        config = EvaluatorConfig(nudge_id="fraud_alert", priority=5)
        custom_eval = FraudAlertEvaluator(config)
        strategy.register_custom_evaluator(custom_eval)
        context = {
            "nudge_id": "fraud_alert",
            "notification_text": "Fraud detected",
            "preview_text": "Review",
            "fraud_detected": True,
        }
        result = await strategy.evaluate(user_id, context)
        assert isinstance(result, NudgeCandidate)
        assert result.priority == 5
