from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from .constants import (
    AssetCategory,
    LiabilityCategory,
    ManualTransactionFrequency,
    ManualTransactionKind,
    VeraPovExpenseCategory,
    VeraPovIncomeCategory,
)


class AssetCreate(BaseModel):
    name: str = Field(min_length=1)
    estimated_value: Decimal = Field(ge=Decimal("0"))
    currency_code: str = Field(min_length=3, max_length=3)
    vera_category: AssetCategory
    is_active: bool = True

    @field_validator("currency_code")
    @classmethod
    def _currency_upper(cls, value: str) -> str:
        return value.upper()


class LiabilityCreate(BaseModel):
    name: str = Field(min_length=1)
    principal_balance: Decimal = Field(ge=Decimal("0"))
    minimum_payment_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    next_payment_due_date: Optional[date] = None
    currency_code: str = Field(min_length=3, max_length=3)
    vera_category: LiabilityCategory
    is_active: bool = True

    @field_validator("currency_code")
    @classmethod
    def _currency_upper(cls, value: str) -> str:
        return value.upper()

    @field_validator("next_payment_due_date")
    @classmethod
    def _due_date_not_past(cls, value: Optional[date]) -> Optional[date]:
        if value is None:
            return value
        if value < date.today():
            raise ValueError("next_payment_due_date must be today or in the future")
        return value


class ManualTransactionCreate(BaseModel):
    kind: ManualTransactionKind
    amount: Decimal = Field(ge=Decimal("0"))
    currency_code: str = Field(min_length=3, max_length=3)
    merchant_or_payee: str = Field(min_length=1)
    taxonomy_category: str
    taxonomy_subcategory: str
    taxonomy_id: str | None = None
    vera_income_category: VeraPovIncomeCategory | None = None
    vera_expense_category: VeraPovExpenseCategory | None = None
    notes: str | None = None
    recurring: bool | None = None
    frequency: ManualTransactionFrequency | None = None

    @field_validator("currency_code")
    @classmethod
    def _currency_upper(cls, value: str) -> str:
        return value.upper()

    @field_validator("vera_income_category", mode="after")
    @classmethod
    def _validate_vera_category(cls, value: VeraPovIncomeCategory | None, info: ValidationInfo) -> VeraPovIncomeCategory | None:
        kind = info.data.get("kind")
        expense_category = info.data.get("vera_expense_category")
        if kind == ManualTransactionKind.INCOME:
            if value is None:
                raise ValueError("vera_income_category is required for income transactions")
            if expense_category is not None:
                raise ValueError("vera_expense_category must be None for income transactions")
        if kind == ManualTransactionKind.EXPENSE:
            if expense_category is None:
                raise ValueError("vera_expense_category is required for expense transactions")
            if value is not None:
                raise ValueError("vera_income_category must be None for expense transactions")
        return value

    @field_validator("frequency", mode="after")
    @classmethod
    def _frequency_requires_recurring(cls, value: ManualTransactionFrequency | None, info: ValidationInfo) -> ManualTransactionFrequency | None:
        recurring = info.data.get("recurring")
        if value is not None and not recurring:
            raise ValueError("frequency requires recurring to be True")
        return value


class NovaMicroIntentResult(BaseModel):
    kind: Literal["asset", "liability", "manual_tx"]
    name: str | None = None
    amount: Decimal | None = None
    currency_code: str | None = None
    date: Optional[date] = None
    merchant_or_payee: str | None = None
    notes: str | None = None
    confidence: float | None = None
    suggested_category: str | None = None
    suggested_vera_income_category: VeraPovIncomeCategory | None = None
    suggested_vera_expense_category: VeraPovExpenseCategory | None = None
    suggested_plaid_category: str | None = None
    suggested_plaid_subcategory: str | None = None


