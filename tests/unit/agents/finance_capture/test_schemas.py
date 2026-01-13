"""Test schema validation for finance capture agent."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.agents.supervisor.finance_capture_agent.constants import (
    AssetCategory,
    LiabilityCategory,
    ManualTransactionFrequency,
    ManualTransactionKind,
    VeraPovExpenseCategory,
    VeraPovIncomeCategory,
)
from app.agents.supervisor.finance_capture_agent.schemas import (
    AssetCreate,
    LiabilityCreate,
    ManualTransactionCreate,
    NovaMicroIntentResult,
)


class TestAssetCreate:
    def test_valid_asset_creation(self):
        asset = AssetCreate(
            name="My House",
            estimated_value=Decimal("500000"),
            currency_code="USD",
            vera_category=AssetCategory.REAL_ESTATE,
        )
        assert asset.name == "My House"
        assert asset.estimated_value == Decimal("500000")
        assert asset.currency_code == "USD"
        assert asset.is_active is True

    def test_currency_code_uppercase_conversion(self):
        asset = AssetCreate(
            name="Car",
            estimated_value=Decimal("30000"),
            currency_code="usd",
            vera_category=AssetCategory.VEHICLES,
        )
        assert asset.currency_code == "USD"

    def test_negative_value_rejected(self):
        with pytest.raises(ValidationError, match="greater than or equal"):
            AssetCreate(
                name="Invalid Asset",
                estimated_value=Decimal("-1000"),
                currency_code="USD",
                vera_category=AssetCategory.OTHER_ASSETS,
            )

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError, match="at least 1 character"):
            AssetCreate(
                name="",
                estimated_value=Decimal("1000"),
                currency_code="USD",
                vera_category=AssetCategory.OTHER_ASSETS,
            )

    def test_invalid_currency_code_length(self):
        with pytest.raises(ValidationError):
            AssetCreate(
                name="Asset",
                estimated_value=Decimal("1000"),
                currency_code="US",
                vera_category=AssetCategory.OTHER_ASSETS,
            )


class TestLiabilityCreate:
    def test_valid_liability_creation(self):
        liability = LiabilityCreate(
            name="Mortgage",
            principal_balance=Decimal("300000"),
            minimum_payment_amount=Decimal("1500"),
            next_payment_due_date=date.today() + timedelta(days=30),
            currency_code="USD",
            vera_category=LiabilityCategory.MORTGAGES,
        )
        assert liability.name == "Mortgage"
        assert liability.principal_balance == Decimal("300000")
        assert liability.minimum_payment_amount == Decimal("1500")

    def test_optional_payment_amount(self):
        liability = LiabilityCreate(
            name="Loan",
            principal_balance=Decimal("5000"),
            currency_code="USD",
            vera_category=LiabilityCategory.LOANS,
        )
        assert liability.minimum_payment_amount is None
        assert liability.next_payment_due_date is None

    def test_past_due_date_rejected(self):
        with pytest.raises(ValidationError, match="must be today or in the future"):
            LiabilityCreate(
                name="Loan",
                principal_balance=Decimal("5000"),
                next_payment_due_date=date.today() - timedelta(days=1),
                currency_code="USD",
                vera_category=LiabilityCategory.LOANS,
            )

    def test_today_due_date_accepted(self):
        liability = LiabilityCreate(
            name="Loan",
            principal_balance=Decimal("5000"),
            next_payment_due_date=date.today(),
            currency_code="USD",
            vera_category=LiabilityCategory.LOANS,
        )
        assert liability.next_payment_due_date == date.today()

    def test_negative_balance_rejected(self):
        with pytest.raises(ValidationError, match="greater than or equal"):
            LiabilityCreate(
                name="Invalid",
                principal_balance=Decimal("-1000"),
                currency_code="USD",
                vera_category=LiabilityCategory.OTHER_LIABILITIES,
            )


class TestManualTransactionCreate:
    def test_valid_income_transaction(self):
        tx = ManualTransactionCreate(
            kind=ManualTransactionKind.INCOME,
            amount=Decimal("5000"),
            currency_code="USD",
            taxonomy_category="Income",
            taxonomy_subcategory="Wages",
            vera_income_category=VeraPovIncomeCategory.SALARY_WAGES,
        )
        assert tx.kind == ManualTransactionKind.INCOME
        assert tx.vera_income_category == VeraPovIncomeCategory.SALARY_WAGES
        assert tx.vera_expense_category is None

    def test_valid_expense_transaction(self):
        tx = ManualTransactionCreate(
            kind=ManualTransactionKind.EXPENSE,
            amount=Decimal("150"),
            currency_code="USD",
            taxonomy_category="Food & Dining",
            taxonomy_subcategory="Restaurant",
            vera_expense_category=VeraPovExpenseCategory.FOOD_DINING,
        )
        assert tx.kind == ManualTransactionKind.EXPENSE
        assert tx.vera_expense_category == VeraPovExpenseCategory.FOOD_DINING
        assert tx.vera_income_category is None

    def test_income_missing_vera_income_category(self):
        with pytest.raises(ValidationError, match="vera_income_category is required"):
            ManualTransactionCreate(
                kind=ManualTransactionKind.INCOME,
                amount=Decimal("5000"),
                currency_code="USD",
                taxonomy_category="Income",
                taxonomy_subcategory="Wages",
            )

    def test_expense_missing_vera_expense_category(self):
        with pytest.raises(ValidationError, match="vera_expense_category is required"):
            ManualTransactionCreate(
                kind=ManualTransactionKind.EXPENSE,
                amount=Decimal("150"),
                currency_code="USD",
                taxonomy_category="Food & Dining",
                taxonomy_subcategory="Restaurant",
            )

    def test_income_with_expense_category_rejected(self):
        with pytest.raises(ValidationError, match="vera_expense_category must be None"):
            ManualTransactionCreate(
                kind=ManualTransactionKind.INCOME,
                amount=Decimal("5000"),
                currency_code="USD",
                taxonomy_category="Income",
                taxonomy_subcategory="Wages",
                vera_income_category=VeraPovIncomeCategory.SALARY_WAGES,
                vera_expense_category=VeraPovExpenseCategory.FOOD_DINING,
            )

    def test_expense_with_income_category_rejected(self):
        with pytest.raises(ValidationError, match="vera_income_category must be None"):
            ManualTransactionCreate(
                kind=ManualTransactionKind.EXPENSE,
                amount=Decimal("150"),
                currency_code="USD",
                taxonomy_category="Food & Dining",
                taxonomy_subcategory="Restaurant",
                vera_expense_category=VeraPovExpenseCategory.FOOD_DINING,
                vera_income_category=VeraPovIncomeCategory.SALARY_WAGES,
            )

    def test_recurring_with_frequency(self):
        tx = ManualTransactionCreate(
            kind=ManualTransactionKind.INCOME,
            amount=Decimal("5000"),
            currency_code="USD",
            taxonomy_category="Income",
            taxonomy_subcategory="Wages",
            vera_income_category=VeraPovIncomeCategory.SALARY_WAGES,
            recurring=True,
            frequency=ManualTransactionFrequency.MONTHLY,
        )
        assert tx.recurring is True
        assert tx.frequency == ManualTransactionFrequency.MONTHLY

    def test_frequency_without_recurring_rejected(self):
        with pytest.raises(ValidationError, match="frequency requires recurring"):
            ManualTransactionCreate(
                kind=ManualTransactionKind.INCOME,
                amount=Decimal("5000"),
                currency_code="USD",
                taxonomy_category="Income",
                taxonomy_subcategory="Wages",
                vera_income_category=VeraPovIncomeCategory.SALARY_WAGES,
                recurring=False,
                frequency=ManualTransactionFrequency.MONTHLY,
            )

    def test_optional_fields(self):
        tx = ManualTransactionCreate(
            kind=ManualTransactionKind.EXPENSE,
            amount=Decimal("100"),
            currency_code="USD",
            taxonomy_category="Food & Dining",
            taxonomy_subcategory="Restaurant",
            vera_expense_category=VeraPovExpenseCategory.FOOD_DINING,
            name="Lunch",
            merchant_or_payee="Restaurant XYZ",
            notes="Team lunch",
        )
        assert tx.name == "Lunch"
        assert tx.merchant_or_payee == "Restaurant XYZ"
        assert tx.notes == "Team lunch"


class TestNovaMicroIntentResult:
    def test_valid_asset_intent(self):
        intent = NovaMicroIntentResult(
            kind="asset",
            name="House",
            amount=Decimal("500000"),
            currency_code="USD",
            suggested_category="Real Estate",
            confidence=0.9,
        )
        assert intent.kind == "asset"
        assert intent.name == "House"
        assert intent.amount == Decimal("500000")

    def test_valid_manual_tx_intent(self):
        intent = NovaMicroIntentResult(
            kind="manual_tx",
            amount=Decimal("150"),
            currency_code="USD",
            merchant_or_payee="Store",
            suggested_plaid_category="Food & Dining",
            suggested_plaid_subcategory="Restaurant",
            suggested_vera_expense_category=VeraPovExpenseCategory.FOOD_DINING,
        )
        assert intent.kind == "manual_tx"
        assert intent.suggested_plaid_category == "Food & Dining"

    def test_minimal_intent(self):
        intent = NovaMicroIntentResult(kind="asset")
        assert intent.kind == "asset"
        assert intent.name is None
        assert intent.amount is None
