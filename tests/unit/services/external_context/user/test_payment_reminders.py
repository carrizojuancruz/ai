"""Unit tests for PaymentRemindersService.

Tests the formatting and retrieval of payment reminders for users.
Follows AAA pattern (Arrange-Act-Assert) and ensures deterministic, fast unit tests.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.external_context.user.payment_reminders import PaymentRemindersService


@pytest.fixture
def service():
    """Fixture providing a PaymentRemindersService instance."""
    return PaymentRemindersService()


@pytest.fixture
def mock_http_client():
    """Mock FOSHttpClient for testing without external dependencies."""
    with patch('app.services.external_context.user.payment_reminders.FOSHttpClient') as mock:
        yield mock


class TestFormatPaymentReminders:
    """Test cases for _format_payment_reminders method."""

    def test_format_monthly_reminder(self, service):
        """Test formatting of monthly reminders."""
        # Arrange
        reminders = [
            {
                "title": "Electricity",
                "status": "active",
                "frequency": "monthly",
                "day_of_month": 15,
            }
        ]

        # Act
        result = service._format_payment_reminders(reminders)

        # Assert
        assert len(result) == 1
        assert result[0]["title"] == "Electricity"
        assert result[0]["status"] == "active"
        assert "monthly on day 15" in result[0]["summary"]

    def test_format_weekly_reminder_with_day_of_week(self, service):
        """Test formatting of weekly reminders with day of week."""
        # Arrange
        reminders = [
            {
                "title": "Gym Membership",
                "status": "active",
                "frequency": "weekly",
                "day_of_week": 0,  # Sunday
            }
        ]

        # Act
        result = service._format_payment_reminders(reminders)

        # Assert
        assert len(result) == 1
        assert result[0]["title"] == "Gym Membership"
        assert "weekly on Sunday" in result[0]["summary"]

    def test_format_weekly_reminder_all_days(self, service):
        """Test formatting of weekly reminders for all days of week."""
        # Arrange
        days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        reminders = [
            {
                "title": f"Task {day}",
                "status": "active",
                "frequency": "weekly",
                "day_of_week": i,
            }
            for i, day in enumerate(days)
        ]

        # Act
        result = service._format_payment_reminders(reminders)

        # Assert
        assert len(result) == 7
        for i, reminder in enumerate(result):
            assert days[i] in reminder["summary"]

    def test_format_yearly_reminder_with_month_and_day(self, service):
        """Test formatting of yearly reminders with month and day."""
        # Arrange
        reminders = [
            {
                "title": "Annual Review",
                "status": "active",
                "frequency": "yearly",
                "month_of_year": 12,
                "day_of_month": 25,
            }
        ]

        # Act
        result = service._format_payment_reminders(reminders)

        # Assert
        assert len(result) == 1
        assert "yearly on 12/25" in result[0]["summary"]

    def test_format_yearly_reminder_with_month_only(self, service):
        """Test formatting of yearly reminders with month only."""
        # Arrange
        reminders = [
            {
                "title": "Birthday",
                "status": "active",
                "frequency": "yearly",
                "month_of_year": 6,
            }
        ]

        # Act
        result = service._format_payment_reminders(reminders)

        # Assert
        assert len(result) == 1
        assert "yearly in month 6" in result[0]["summary"]

    def test_format_reminder_with_next_run_at(self, service):
        """Test formatting includes next_run_at timestamp."""
        # Arrange
        reminders = [
            {
                "title": "Bill Payment",
                "status": "active",
                "frequency": "monthly",
                "day_of_month": 1,
                "next_run_at": "2026-02-01T10:00:00Z",
            }
        ]

        # Act
        result = service._format_payment_reminders(reminders)

        # Assert
        assert len(result) == 1
        assert "next scheduled for 2026-02-01T10:00:00Z" in result[0]["summary"]

    def test_format_reminder_with_last_triggered_at(self, service):
        """Test formatting includes last_triggered_at timestamp."""
        # Arrange
        reminders = [
            {
                "title": "Insurance",
                "status": "active",
                "frequency": "monthly",
                "day_of_month": 10,
                "last_triggered_at": "2026-01-10T10:00:00Z",
            }
        ]

        # Act
        result = service._format_payment_reminders(reminders)

        # Assert
        assert len(result) == 1
        assert "last sent 2026-01-10T10:00:00Z" in result[0]["summary"]

    def test_format_reminder_with_amount_and_currency(self, service):
        """Test formatting includes amount and currency."""
        # Arrange
        reminders = [
            {
                "title": "Rent",
                "status": "active",
                "frequency": "monthly",
                "day_of_month": 1,
                "amount": 1500,
                "currency_code": "USD",
            }
        ]

        # Act
        result = service._format_payment_reminders(reminders)

        # Assert
        assert len(result) == 1
        assert "amount 1500 USD" in result[0]["summary"]

    def test_format_reminder_with_amount_only(self, service):
        """Test formatting with amount but no currency."""
        # Arrange
        reminders = [
            {
                "title": "Fee",
                "status": "active",
                "frequency": "monthly",
                "day_of_month": 15,
                "amount": 50,
            }
        ]

        # Act
        result = service._format_payment_reminders(reminders)

        # Assert
        assert len(result) == 1
        assert "amount 50" in result[0]["summary"]

    def test_format_reminder_with_description(self, service):
        """Test formatting includes description."""
        # Arrange
        reminders = [
            {
                "title": "Subscription",
                "status": "active",
                "frequency": "monthly",
                "day_of_month": 20,
                "description": "Netflix monthly subscription",
            }
        ]

        # Act
        result = service._format_payment_reminders(reminders)

        # Assert
        assert len(result) == 1
        assert "Netflix monthly subscription" in result[0]["summary"]

    def test_format_paused_reminder(self, service):
        """Test formatting of paused reminders."""
        # Arrange
        reminders = [
            {
                "title": "Gym Membership",
                "status": "paused",
                "frequency": "weekly",
                "day_of_week": 1,
            }
        ]

        # Act
        result = service._format_payment_reminders(reminders)

        # Assert
        assert len(result) == 1
        assert result[0]["status"] == "paused"
        assert "paused" in result[0]["summary"]

    def test_format_reminder_with_missing_title(self, service):
        """Test formatting uses default title when missing."""
        # Arrange
        reminders = [
            {
                "status": "active",
                "frequency": "monthly",
                "day_of_month": 5,
            }
        ]

        # Act
        result = service._format_payment_reminders(reminders)

        # Assert
        assert len(result) == 1
        assert result[0]["title"] == "Reminder"

    def test_format_reminder_with_missing_status(self, service):
        """Test formatting uses unknown status when missing."""
        # Arrange
        reminders = [
            {
                "title": "Test",
                "frequency": "monthly",
                "day_of_month": 5,
            }
        ]

        # Act
        result = service._format_payment_reminders(reminders)

        # Assert
        assert len(result) == 1
        assert result[0]["status"] == "unknown"

    def test_format_multiple_reminders(self, service):
        """Test formatting multiple reminders at once."""
        # Arrange
        reminders = [
            {
                "title": "Rent",
                "status": "active",
                "frequency": "monthly",
                "day_of_month": 1,
            },
            {
                "title": "Gym",
                "status": "paused",
                "frequency": "weekly",
                "day_of_week": 3,
            },
            {
                "title": "Insurance",
                "status": "active",
                "frequency": "yearly",
                "month_of_year": 6,
                "day_of_month": 15,
            },
        ]

        # Act
        result = service._format_payment_reminders(reminders)

        # Assert
        assert len(result) == 3
        assert result[0]["title"] == "Rent"
        assert result[1]["title"] == "Gym"
        assert result[2]["title"] == "Insurance"

    def test_format_empty_reminders_list(self, service):
        """Test formatting empty reminders list."""
        # Arrange
        reminders = []

        # Act
        result = service._format_payment_reminders(reminders)

        # Assert
        assert result == []

    def test_format_custom_frequency(self, service):
        """Test formatting with custom frequency string."""
        # Arrange
        reminders = [
            {
                "title": "Custom",
                "status": "active",
                "frequency": "bi-weekly",
            }
        ]

        # Act
        result = service._format_payment_reminders(reminders)

        # Assert
        assert len(result) == 1
        assert "bi-weekly" in result[0]["summary"]


class TestGetPaymentReminders:
    """Test cases for get_payment_reminders method."""

    @pytest.mark.asyncio
    async def test_success_with_reminders(self, service, mock_http_client):
        """Test successful fetch of payment reminders."""
        # Arrange
        mock_client_instance = AsyncMock()
        mock_http_client.return_value = mock_client_instance
        service.http_client = mock_client_instance

        mock_client_instance.get.return_value = {
            "reminders": [
                {
                    "title": "Gub",
                    "status": "active",
                    "frequency": "monthly",
                    "day_of_month": 1,
                },
                {
                    "title": "Buen",
                    "status": "active",
                    "frequency": "monthly",
                    "day_of_month": 1,
                },
            ],
            "total_count": 2,
        }

        # Act
        result = await service.get_payment_reminders("user_123")

        # Assert
        assert "payment_reminders" in result
        assert len(result["payment_reminders"]) == 2
        assert result["payment_reminders"][0]["title"] == "Gub"
        assert result["payment_reminders"][1]["title"] == "Buen"
        mock_client_instance.get.assert_called_once_with(
            "/internal/payment_reminders/user_123"
        )

    @pytest.mark.asyncio
    async def test_success_with_empty_reminders(self, service, mock_http_client):
        """Test successful fetch with no reminders."""
        # Arrange
        mock_client_instance = AsyncMock()
        mock_http_client.return_value = mock_client_instance
        service.http_client = mock_client_instance

        mock_client_instance.get.return_value = {
            "reminders": [],
            "total_count": 0,
        }

        # Act
        result = await service.get_payment_reminders("user_123")

        # Assert
        assert "payment_reminders" in result
        assert result["payment_reminders"] == []

    @pytest.mark.asyncio
    async def test_success_with_mixed_status_reminders(self, service, mock_http_client):
        """Test fetch with both active and paused reminders."""
        # Arrange
        mock_client_instance = AsyncMock()
        mock_http_client.return_value = mock_client_instance
        service.http_client = mock_client_instance

        mock_client_instance.get.return_value = {
            "reminders": [
                {
                    "title": "Active Reminder",
                    "status": "active",
                    "frequency": "monthly",
                    "day_of_month": 15,
                },
                {
                    "title": "Paused Reminder",
                    "status": "paused",
                    "frequency": "weekly",
                    "day_of_week": 0,
                },
            ],
            "total_count": 2,
        }

        # Act
        result = await service.get_payment_reminders("user_456")

        # Assert
        assert "payment_reminders" in result
        assert len(result["payment_reminders"]) == 2
        assert result["payment_reminders"][0]["status"] == "active"
        assert result["payment_reminders"][1]["status"] == "paused"

    @pytest.mark.asyncio
    async def test_http_client_error(self, service, mock_http_client):
        """Test graceful handling of HTTP client errors."""
        # Arrange
        mock_client_instance = AsyncMock()
        mock_http_client.return_value = mock_client_instance
        service.http_client = mock_client_instance
        mock_client_instance.get.side_effect = Exception("Connection failed")

        # Act
        result = await service.get_payment_reminders("user_123")

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_missing_reminders_key_in_response(self, service, mock_http_client):
        """Test handling of response missing reminders key."""
        # Arrange
        mock_client_instance = AsyncMock()
        mock_http_client.return_value = mock_client_instance
        service.http_client = mock_client_instance

        mock_client_instance.get.return_value = {"total_count": 0}

        # Act
        result = await service.get_payment_reminders("user_123")

        # Assert
        assert "payment_reminders" in result
        assert result["payment_reminders"] == []

    @pytest.mark.asyncio
    async def test_with_complete_reminder_data(self, service, mock_http_client):
        """Test fetch with complete reminder data including all fields."""
        # Arrange
        mock_client_instance = AsyncMock()
        mock_http_client.return_value = mock_client_instance
        service.http_client = mock_client_instance

        mock_client_instance.get.return_value = {
            "reminders": [
                {
                    "id": "rem_123",
                    "title": "Complete Reminder",
                    "description": "Full details",
                    "amount": 500,
                    "currency_code": "USD",
                    "frequency": "monthly",
                    "day_of_month": 5,
                    "status": "active",
                    "next_run_at": "2026-02-05T10:00:00Z",
                    "last_triggered_at": "2026-01-05T10:00:00Z",
                },
            ],
            "total_count": 1,
        }

        # Act
        result = await service.get_payment_reminders("user_123")

        # Assert
        assert "payment_reminders" in result
        assert len(result["payment_reminders"]) == 1
        reminder = result["payment_reminders"][0]
        assert reminder["title"] == "Complete Reminder"
        assert "amount 500 USD" in reminder["summary"]
        assert "next scheduled for 2026-02-05T10:00:00Z" in reminder["summary"]
        assert "last sent 2026-01-05T10:00:00Z" in reminder["summary"]

    @pytest.mark.asyncio
    async def test_timeout_error(self, service, mock_http_client):
        """Test handling of timeout errors."""
        # Arrange
        mock_client_instance = AsyncMock()
        mock_http_client.return_value = mock_client_instance
        service.http_client = mock_client_instance
        mock_client_instance.get.side_effect = TimeoutError("Request timeout")

        # Act
        result = await service.get_payment_reminders("user_123")

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_different_user_ids(self, service, mock_http_client):
        """Test that different user IDs are used in API calls."""
        # Arrange
        mock_client_instance = AsyncMock()
        mock_http_client.return_value = mock_client_instance
        service.http_client = mock_client_instance
        mock_client_instance.get.return_value = {"reminders": [], "total_count": 0}

        # Act
        await service.get_payment_reminders("user_111")
        await service.get_payment_reminders("user_222")

        # Assert
        calls = mock_client_instance.get.call_args_list
        assert len(calls) == 2
        assert calls[0][0][0] == "/internal/payment_reminders/user_111"
        assert calls[1][0][0] == "/internal/payment_reminders/user_222"
