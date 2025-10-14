"""
Unit tests for app.services.nudges.strategies.bill_strategy module.

Tests cover:
- BillNudgeStrategy initialization
- Properties (nudge_type, requires_fos_text)
- evaluate method with various scenarios
- get_priority method
- validate_conditions method
- Error handling
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.nudges.strategies.bill_strategy import BillNudgeStrategy


@pytest.fixture
def mock_plaid_service():
    """Fixture to mock the Plaid bills service."""
    with patch("app.services.nudges.strategies.bill_strategy.get_plaid_bills_service") as mock_get:
        mock_service = MagicMock()
        mock_get.return_value = mock_service
        yield mock_service


class TestBillNudgeStrategy:
    """Test BillNudgeStrategy class."""

    def test_init_gets_plaid_bills_service(self, mock_plaid_service):
        """Test initialization gets plaid bills service."""
        strategy = BillNudgeStrategy()
        assert strategy.bills_service == mock_plaid_service

    def test_nudge_type_property(self):
        """Test nudge_type property returns correct value."""
        strategy = BillNudgeStrategy()
        assert strategy.nudge_type == "static_bill"

    def test_requires_fos_text_property(self):
        """Test requires_fos_text property returns False."""
        strategy = BillNudgeStrategy()
        assert strategy.requires_fos_text is False


class TestBillNudgeStrategyEvaluate:
    """Test evaluate method."""

    @pytest.mark.asyncio
    async def test_evaluate_no_bills_found(self, mock_plaid_service):
        """Test evaluate when no bills are found."""
        user_id = uuid4()
        mock_plaid_service.get_upcoming_bills = AsyncMock(return_value=[])

        strategy = BillNudgeStrategy()
        result = await strategy.evaluate(user_id, {})

        assert result is None
        mock_plaid_service.get_upcoming_bills.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_evaluate_bills_found_creates_candidate(self, mock_plaid_service):
        """Test evaluate creates candidate when bills are found."""
        user_id = uuid4()

        # Mock bill object
        mock_bill = MagicMock()
        mock_bill.account_name = "Credit Card"
        mock_bill.institution_name = "Bank of America"
        mock_bill.next_payment_due_date = datetime(2024, 1, 15, tzinfo=timezone.utc)
        mock_bill.minimum_payment_amount = 150.0
        mock_bill.days_until_due = 5
        mock_bill.to_dict.return_value = {"account": "Credit Card", "amount": 150.0}

        mock_plaid_service.get_upcoming_bills = AsyncMock(return_value=[mock_bill])
        mock_plaid_service.calculate_priority.return_value = 8
        mock_plaid_service.generate_notification = AsyncMock(return_value={
            "notification_text": "Your bill is due soon",
            "preview_text": "Bill reminder"
        })

        strategy = BillNudgeStrategy()
        result = await strategy.evaluate(user_id, {})

        assert result is not None
        assert result.user_id == user_id
        assert result.nudge_type == "static_bill"
        assert result.priority == 8
        assert result.notification_text == "Your bill is due soon"
        assert result.preview_text == "Bill reminder"
        assert result.metadata["bill"] == {"account": "Credit Card", "amount": 150.0}
        assert result.metadata["total_bills_detected"] == 1
        assert result.metadata["data_source"] == "plaid_liabilities"
        assert result.metadata["is_predicted"] is False

        mock_plaid_service.get_upcoming_bills.assert_called_once_with(user_id)
        mock_plaid_service.calculate_priority.assert_called_once_with(mock_bill)
        mock_plaid_service.generate_notification.assert_called_once_with(mock_bill)

    @pytest.mark.asyncio
    async def test_evaluate_multiple_bills_uses_most_urgent(self, mock_plaid_service):
        """Test evaluate uses the most urgent bill when multiple bills exist."""
        user_id = uuid4()

        # Mock bills - first is most urgent
        mock_bill1 = MagicMock()
        mock_bill1.account_name = "Credit Card"
        mock_bill1.next_payment_due_date = datetime(2024, 1, 10, tzinfo=timezone.utc)
        mock_bill1.days_until_due = 2
        mock_bill1.to_dict.return_value = {"account": "Credit Card"}

        mock_bill2 = MagicMock()
        mock_bill2.account_name = "Loan"
        mock_bill2.next_payment_due_date = datetime(2024, 1, 20, tzinfo=timezone.utc)
        mock_bill2.days_until_due = 12

        mock_plaid_service.get_upcoming_bills = AsyncMock(return_value=[mock_bill1, mock_bill2])
        mock_plaid_service.calculate_priority.return_value = 9
        mock_plaid_service.generate_notification = AsyncMock(return_value={
            "notification_text": "Credit card payment due",
            "preview_text": "Credit card reminder"
        })

        strategy = BillNudgeStrategy()
        result = await strategy.evaluate(user_id, {})

        assert result is not None
        assert result.notification_text == "Credit card payment due"
        assert result.metadata["bill"] == {"account": "Credit Card"}

        # Should use first bill (most urgent)
        mock_plaid_service.generate_notification.assert_called_once_with(mock_bill1)
    @pytest.mark.asyncio
    async def test_evaluate_handles_exception(self, mock_plaid_service):
        """Test evaluate handles exceptions gracefully."""
        """Test evaluate handles exceptions gracefully."""
        user_id = uuid4()
        mock_plaid_service.get_upcoming_bills = AsyncMock(side_effect=Exception("Service error"))

        strategy = BillNudgeStrategy()
        result = await strategy.evaluate(user_id, {})

        assert result is None
        mock_plaid_service.get_upcoming_bills.assert_called_once_with(user_id)


class TestBillNudgeStrategyGetPriority:
    """Test get_priority method."""

    def test_get_priority_with_bill(self, mock_plaid_service):
        """Test get_priority delegates to bills service."""
        mock_bill = MagicMock()
        mock_plaid_service.calculate_priority.return_value = 7

        strategy = BillNudgeStrategy()
        result = strategy.get_priority({"bill": mock_bill})

        assert result == 7
        mock_plaid_service.calculate_priority.assert_called_once_with(mock_bill)

    def test_get_priority_no_bill(self, mock_plaid_service):
        """Test get_priority returns default when no bill."""
        strategy = BillNudgeStrategy()
        result = strategy.get_priority({})

        assert result == 2
        mock_plaid_service.calculate_priority.assert_not_called()

    def test_get_priority_none_bill(self, mock_plaid_service):
        """Test get_priority returns default when bill is None."""
        strategy = BillNudgeStrategy()
        result = strategy.get_priority({"bill": None})

        assert result == 2
        mock_plaid_service.calculate_priority.assert_not_called()


class TestBillNudgeStrategyValidateConditions:
    @pytest.mark.asyncio
    async def test_validate_conditions_always_true(self, mock_plaid_service):
        """Test validate_conditions always returns True."""
        user_id = uuid4()

        strategy = BillNudgeStrategy()
        result = await strategy.validate_conditions(user_id)

        assert result is True
