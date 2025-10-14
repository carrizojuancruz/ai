from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.nudges.plaid_bills import PlaidBill, PlaidBillsService, get_plaid_bills_service


class TestPlaidBill:

    def test_initialization_with_required_fields(self):
        due_date = datetime.now() + timedelta(days=5)
        bill = PlaidBill(
            account_name="Chase Credit Card",
            institution_name="Chase",
            account_type="Credit",
            next_payment_due_date=due_date,
            minimum_payment_amount=150.00,
        )

        assert bill.account_name == "Chase Credit Card"
        assert bill.institution_name == "Chase"
        assert bill.minimum_payment_amount == 150.00
        assert bill.last_payment_date is None
        assert bill.is_overdue is False
        assert bill.days_until_due == 5

    def test_initialization_with_optional_fields(self):
        due_date = datetime.now() + timedelta(days=3)
        last_payment = datetime.now() - timedelta(days=30)

        bill = PlaidBill(
            account_name="Amex Gold",
            institution_name="American Express",
            account_type="Credit",
            next_payment_due_date=due_date,
            minimum_payment_amount=250.50,
            last_payment_date=last_payment,
            last_payment_amount=250.50,
            account_id="acc_123",
        )

        assert bill.last_payment_date == last_payment
        assert bill.last_payment_amount == 250.50
        assert bill.account_id == "acc_123"

    @pytest.mark.parametrize("days_offset,expected_days", [
        (10, 10),
        (0, 0),
        (-2, -2),
    ])
    def test_days_until_due_calculation(self, days_offset, expected_days):
        bill = PlaidBill(
            account_name="Test",
            institution_name="Test Bank",
            account_type="Credit",
            next_payment_due_date=datetime.now() + timedelta(days=days_offset),
            minimum_payment_amount=100.00,
        )
        assert bill.days_until_due == expected_days

    def test_to_dict_complete_data(self):
        due_date = datetime(2025, 10, 20, 12, 0, 0)
        last_payment = datetime(2025, 9, 20, 12, 0, 0)

        bill = PlaidBill(
            account_name="Capital One Venture",
            institution_name="Capital One",
            account_type="Credit - Travel",
            next_payment_due_date=due_date,
            minimum_payment_amount=175.25,
            last_payment_date=last_payment,
            last_payment_amount=200.00,
            account_id="acc_789",
        )

        result = bill.to_dict()

        assert result["account_name"] == "Capital One Venture"
        assert result["next_payment_due_date"] == due_date.isoformat()
        assert result["minimum_payment_amount"] == 175.25
        assert result["last_payment_date"] == last_payment.isoformat()
        assert result["last_payment_amount"] == 200.00

    def test_to_dict_minimal_data(self):
        bill = PlaidBill(
            account_name="Simple Card",
            institution_name="Simple Bank",
            account_type="Credit",
            next_payment_due_date=datetime(2025, 10, 25),
            minimum_payment_amount=50.00,
        )

        result = bill.to_dict()

        assert result["last_payment_date"] is None
        assert result["last_payment_amount"] is None
        assert result["account_id"] is None


class TestPlaidBillsService:

    @pytest.fixture
    def mock_db_service(self):
        mock_service = MagicMock()
        mock_session = AsyncMock()
        mock_repo = AsyncMock()

        mock_service.get_session.return_value.__aenter__.return_value = mock_session
        mock_service.get_finance_repository.return_value = mock_repo

        return mock_service, mock_session, mock_repo

    @pytest.fixture
    def service_with_mock_db(self, mock_db_service):
        with patch("app.services.nudges.plaid_bills.get_database_service") as mock_get_db:
            mock_get_db.return_value = mock_db_service[0]
            service = PlaidBillsService()
            return service, mock_db_service

    @pytest.mark.asyncio
    async def test_get_upcoming_bills_success(self, service_with_mock_db):
        service, (mock_db_service, mock_session, mock_repo) = service_with_mock_db
        user_id = uuid4()

        mock_query_results = [
            {
                "account_id": "acc_1",
                "account_name": "Chase Sapphire",
                "institution_name": "Chase",
                "account_type": "credit",
                "account_subtype": "credit_card",
                "next_payment_due_date": datetime.now() + timedelta(days=5),
                "minimum_payment_amount": 150.00,
                "last_payment_date": datetime.now() - timedelta(days=30),
                "last_payment_amount": 150.00,
                "current_balance": 1500.00,
                "is_overdue": False,
            },
        ]

        mock_repo.execute_query.return_value = mock_query_results

        bills = await service.get_upcoming_bills(user_id)

        assert len(bills) == 1
        assert bills[0].account_name == "Chase Sapphire"
        assert bills[0].minimum_payment_amount == 150.00

        mock_repo.execute_query.assert_called_once()
        call_kwargs = mock_repo.execute_query.call_args[1]
        assert call_kwargs["user_id"] == str(user_id)
        assert call_kwargs["account_types"] == ["credit", "loan"]

    @pytest.mark.asyncio
    async def test_get_upcoming_bills_empty_results(self, service_with_mock_db):
        service, (_, _, mock_repo) = service_with_mock_db
        mock_repo.execute_query.return_value = []

        bills = await service.get_upcoming_bills(uuid4())

        assert bills == []

    @pytest.mark.asyncio
    async def test_get_upcoming_bills_filters_invalid_amounts(self, service_with_mock_db):
        service, (_, _, mock_repo) = service_with_mock_db

        mock_query_results = [
            {
                "account_id": "acc_1",
                "account_name": "Valid Bill",
                "institution_name": "Chase",
                "account_type": "credit",
                "account_subtype": None,
                "next_payment_due_date": datetime.now() + timedelta(days=5),
                "minimum_payment_amount": 100.00,
                "last_payment_date": None,
                "last_payment_amount": None,
                "current_balance": 1000.00,
                "is_overdue": False,
            },
            {
                "account_id": "acc_2",
                "account_name": "Zero Amount",
                "institution_name": "Bank",
                "account_type": "credit",
                "account_subtype": None,
                "next_payment_due_date": datetime.now() + timedelta(days=5),
                "minimum_payment_amount": 0.00,
                "last_payment_date": None,
                "last_payment_amount": None,
                "current_balance": 0.00,
                "is_overdue": False,
            },
            {
                "account_id": "acc_3",
                "account_name": "None Amount",
                "institution_name": "Bank",
                "account_type": "credit",
                "account_subtype": None,
                "next_payment_due_date": datetime.now() + timedelta(days=5),
                "minimum_payment_amount": None,
                "last_payment_date": None,
                "last_payment_amount": None,
                "current_balance": 0.00,
                "is_overdue": False,
            },
        ]

        mock_repo.execute_query.return_value = mock_query_results

        bills = await service.get_upcoming_bills(uuid4())

        assert len(bills) == 1
        assert bills[0].account_name == "Valid Bill"

    @pytest.mark.asyncio
    async def test_get_upcoming_bills_handles_exception(self, service_with_mock_db):
        service, (_, _, mock_repo) = service_with_mock_db
        mock_repo.execute_query.side_effect = Exception("Database error")

        bills = await service.get_upcoming_bills(uuid4())

        assert bills == []

    def test_parse_bills_with_valid_data(self):
        service = PlaidBillsService()
        query_results = [
            {
                "account_id": "acc_123",
                "account_name": "Test Card",
                "institution_name": "Test Bank",
                "account_type": "credit",
                "account_subtype": "credit_card",
                "next_payment_due_date": datetime(2025, 10, 20),
                "minimum_payment_amount": 100.00,
                "last_payment_date": datetime(2025, 9, 20),
                "last_payment_amount": 100.00,
                "is_overdue": False,
            }
        ]

        bills = service._parse_bills(query_results)

        assert len(bills) == 1
        assert bills[0].account_name == "Test Card"
        assert bills[0].account_type == "Credit - Credit Card"

    def test_parse_bills_filters_invalid_amounts(self):
        service = PlaidBillsService()
        query_results = [
            {
                "account_name": "Valid",
                "institution_name": "Bank",
                "account_type": "credit",
                "account_subtype": None,
                "next_payment_due_date": datetime.now(),
                "minimum_payment_amount": 50.00,
                "is_overdue": False,
            },
            {
                "account_name": "Zero",
                "institution_name": "Bank",
                "account_type": "credit",
                "account_subtype": None,
                "next_payment_due_date": datetime.now(),
                "minimum_payment_amount": 0.00,
                "is_overdue": False,
            },
        ]

        bills = service._parse_bills(query_results)

        assert len(bills) == 1
        assert bills[0].account_name == "Valid"

    @pytest.mark.parametrize("account_type,subtype,expected", [
        ("credit", "credit_card", "Credit - Credit Card"),
        ("loan", None, "Loan"),
        ("loan", "student_loan", "Loan - Student Loan"),
    ])
    def test_format_account_type(self, account_type, subtype, expected):
        result = PlaidBillsService._format_account_type(account_type, subtype)
        assert result == expected

    @pytest.mark.parametrize("days_offset,is_overdue,expected_priority", [
        (-1, True, 5),
        (0, False, 5),
        (1, False, 5),
        (3, False, 4),
        (7, False, 3),
        (14, False, 2),
        (20, False, 1),
    ])
    def test_calculate_priority(self, days_offset, is_overdue, expected_priority):
        service = PlaidBillsService()
        bill = PlaidBill(
            account_name="Test",
            institution_name="Test Bank",
            account_type="Credit",
            next_payment_due_date=datetime.now() + timedelta(days=days_offset),
            minimum_payment_amount=100.00,
            is_overdue=is_overdue,
        )

        priority = service.calculate_priority(bill)

        assert priority == expected_priority

    @pytest.mark.asyncio
    async def test_generate_notification_overdue(self):
        service = PlaidBillsService()
        bill = PlaidBill(
            account_name="Chase Credit Card",
            institution_name="Chase",
            account_type="Credit",
            next_payment_due_date=datetime.now() - timedelta(days=2),
            minimum_payment_amount=150.00,
            is_overdue=True,
        )

        notification = await service.generate_notification(bill)

        assert "OVERDUE" in notification["preview_text"]
        assert "URGENT" in notification["notification_text"]
        assert "$150.00" in notification["notification_text"]
        assert "[Chase]" in notification["notification_text"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("days_offset,expected_in_text", [
        (0, "due TODAY"),
        (1, "due tomorrow"),
        (3, "3 days"),
        (10, "Heads up"),
    ])
    async def test_generate_notification_various_timeframes(self, days_offset, expected_in_text):
        service = PlaidBillsService()
        bill = PlaidBill(
            account_name="Test Card",
            institution_name="Test Bank",
            account_type="Credit",
            next_payment_due_date=datetime.now() + timedelta(days=days_offset),
            minimum_payment_amount=100.00,
        )

        notification = await service.generate_notification(bill)

        assert expected_in_text in notification["notification_text"]

    @pytest.mark.asyncio
    async def test_generate_notification_with_user_name(self):
        service = PlaidBillsService()
        bill = PlaidBill(
            account_name="Test Card",
            institution_name="Test Bank",
            account_type="Credit",
            next_payment_due_date=datetime.now() + timedelta(days=1),
            minimum_payment_amount=100.00,
        )

        notification = await service.generate_notification(bill, user_name="John")

        assert "Hi John!" in notification["notification_text"]


class TestGetPlaidBillsService:

    def test_singleton_pattern(self):
        service1 = get_plaid_bills_service()
        service2 = get_plaid_bills_service()

        assert service1 is service2
        assert isinstance(service1, PlaidBillsService)
