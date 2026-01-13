"""Test helper functions for finance capture agent."""

from decimal import Decimal

import pytest

from app.agents.supervisor.finance_capture_agent.constants import (
    AssetCategory,
    LiabilityCategory,
    VeraPovExpenseCategory,
    VeraPovIncomeCategory,
    to_fos_category,
)
from app.agents.supervisor.finance_capture_agent.helpers import (
    asset_payload_from_draft,
    asset_payload_to_fos,
    build_confirmation_summary,
    choose_from_taxonomy,
    derive_vera_expense,
    derive_vera_income,
    liability_payload_from_draft,
    liability_payload_to_fos,
    manual_tx_payload_from_draft,
    manual_tx_payload_to_fos,
    match_vera_expense_to_plaid,
    match_vera_income_to_plaid,
    normalize_basic_fields,
    safe_normalize_string,
    safe_str_equal,
    seed_draft_from_intent,
)
from app.agents.supervisor.finance_capture_agent.schemas import NovaMicroIntentResult


class TestSafeNormalizeString:
    def test_normalize_basic_string(self):
        assert safe_normalize_string("Hello World") == "hello world"

    def test_normalize_none(self):
        assert safe_normalize_string(None) is None

    def test_normalize_strips_whitespace(self):
        assert safe_normalize_string("  test  ") == "test"

    def test_normalize_special_characters(self):
        result = safe_normalize_string("Café & Restaurant")
        assert "caf" in result.lower()


class TestSafeStrEqual:
    def test_equal_strings(self):
        assert safe_str_equal("test", "TEST") is True

    def test_not_equal_strings(self):
        assert safe_str_equal("test", "other") is False

    def test_none_values(self):
        assert safe_str_equal(None, None) is True
        assert safe_str_equal("test", None) is False
        assert safe_str_equal(None, "test") is False

    def test_whitespace_handling(self):
        assert safe_str_equal("  test  ", "TEST") is True


class TestNormalizeBasicFields:
    def test_normalize_currency_code(self):
        draft = {"currency_code": "usd"}
        normalize_basic_fields(draft)
        assert draft["currency_code"] == "USD"

    def test_normalize_estimated_value(self):
        draft = {"estimated_value": 50000}
        normalize_basic_fields(draft)
        assert draft["estimated_value"] == "50000"

    def test_normalize_decimal_values(self):
        draft = {
            "principal_balance": Decimal("10000"),
            "minimum_payment_amount": 500,
            "amount": "250.50",
        }
        normalize_basic_fields(draft)
        assert draft["principal_balance"] == "10000"
        assert draft["minimum_payment_amount"] == "500"
        assert draft["amount"] == "250.50"

    def test_handles_none_values(self):
        draft = {"estimated_value": None}
        normalize_basic_fields(draft)
        assert draft["estimated_value"] is None


class TestSeedDraftFromIntent:
    def test_seed_asset_draft(self):
        intent = NovaMicroIntentResult(
            kind="asset",
            name="House",
            amount=Decimal("500000"),
            currency_code="USD",
            suggested_category="Real Estate",
        )
        draft = seed_draft_from_intent(intent)
        assert draft["entity_kind"] == "asset"
        assert draft["name"] == "House"
        assert draft["estimated_value"] == "500000"
        assert draft["currency_code"] == "USD"
        assert draft["vera_category"] == "Real Estate"

    def test_seed_liability_draft(self):
        intent = NovaMicroIntentResult(
            kind="liability",
            name="Mortgage",
            amount=Decimal("300000"),
            currency_code="USD",
            suggested_category="Mortgages",
        )
        draft = seed_draft_from_intent(intent)
        assert draft["entity_kind"] == "liability"
        assert draft["name"] == "Mortgage"
        assert draft["principal_balance"] == "300000"
        assert draft["currency_code"] == "USD"

    def test_seed_manual_tx_draft(self):
        intent = NovaMicroIntentResult(
            kind="manual_tx",
            amount=Decimal("150"),
            currency_code="USD",
            merchant_or_payee="Restaurant",
            suggested_plaid_category="Food & Dining",
            suggested_plaid_subcategory="Restaurant",
            suggested_vera_expense_category=VeraPovExpenseCategory.FOOD_DINING,
        )
        draft = seed_draft_from_intent(intent)
        assert draft["entity_kind"] == "manual_tx"
        assert draft["amount"] == "150"
        assert draft["merchant_or_payee"] == "Restaurant"
        assert draft["vera_expense_category"] == VeraPovExpenseCategory.FOOD_DINING


class TestAssetPayloadFromDraft:
    def test_asset_payload_basic(self):
        draft = {
            "name": "Car",
            "estimated_value": "30000",
            "currency_code": "USD",
            "vera_category": AssetCategory.VEHICLES,
        }
        payload = asset_payload_from_draft(draft)
        assert payload["name"] == "Car"
        assert payload["estimated_value"] == 30000.0
        assert payload["currency_code"] == "USD"
        assert payload["vera_category"] == AssetCategory.VEHICLES
        assert payload["is_active"] is True

    def test_asset_payload_defaults(self):
        draft = {"name": "Test"}
        payload = asset_payload_from_draft(draft)
        assert payload["name"] == "Test"
        assert payload["estimated_value"] == 0.0
        assert payload["currency_code"] == "USD"
        assert payload["vera_category"] == AssetCategory.OTHER_ASSETS


class TestLiabilityPayloadFromDraft:
    def test_liability_payload_complete(self):
        draft = {
            "name": "Mortgage",
            "principal_balance": "300000",
            "minimum_payment_amount": "1500",
            "currency_code": "USD",
            "vera_category": LiabilityCategory.MORTGAGES,
        }
        payload = liability_payload_from_draft(draft)
        assert payload["name"] == "Mortgage"
        assert payload["principal_balance"] == 300000.0
        assert payload["minimum_payment_amount"] == 1500.0
        assert payload["currency_code"] == "USD"

    def test_liability_payload_optional_payment(self):
        draft = {
            "name": "Loan",
            "principal_balance": "5000",
            "currency_code": "USD",
        }
        payload = liability_payload_from_draft(draft)
        assert payload["minimum_payment_amount"] is None


class TestManualTxPayloadFromDraft:
    def test_manual_tx_income_payload(self):
        draft = {
            "kind": "income",
            "amount": "5000",
            "currency_code": "USD",
            "taxonomy_category": "Income",
            "taxonomy_subcategory": "Wages",
            "vera_income_category": VeraPovIncomeCategory.SALARY_WAGES,
        }
        payload = manual_tx_payload_from_draft(draft)
        assert payload["kind"] == "income"
        assert payload["amount"] == 5000.0
        assert payload["vera_income_category"] == VeraPovIncomeCategory.SALARY_WAGES.value

    def test_manual_tx_expense_payload(self):
        draft = {
            "kind": "expense",
            "amount": "150",
            "currency_code": "USD",
            "taxonomy_category": "Food & Dining",
            "taxonomy_subcategory": "Restaurant",
            "vera_expense_category": VeraPovExpenseCategory.FOOD_DINING,
            "merchant_or_payee": "Restaurant XYZ",
        }
        payload = manual_tx_payload_from_draft(draft)
        assert payload["kind"] == "expense"
        assert payload["vera_expense_category"] == VeraPovExpenseCategory.FOOD_DINING.value
        assert payload["merchant_or_payee"] == "Restaurant XYZ"


class TestAssetPayloadToFOS:
    def test_converts_vera_category_to_fos_format(self):
        validated = {
            "name": "House",
            "estimated_value": 500000,
            "currency_code": "USD",
            "vera_category": AssetCategory.REAL_ESTATE,
        }
        fos_payload = asset_payload_to_fos(validated)
        assert fos_payload["category"] == "real_estate"
        assert "vera_category" not in fos_payload


class TestLiabilityPayloadToFOS:
    def test_converts_vera_category_to_fos_format(self):
        validated = {
            "name": "Mortgage",
            "principal_balance": 300000,
            "currency_code": "USD",
            "vera_category": LiabilityCategory.MORTGAGES,
        }
        fos_payload = liability_payload_to_fos(validated)
        assert fos_payload["category"] == "mortgages"
        assert "vera_category" not in fos_payload


class TestManualTxPayloadToFOS:
    def test_converts_vera_categories_to_plaid(self):
        validated = {
            "kind": "expense",
            "amount": 150,
            "currency_code": "USD",
            "taxonomy_category": "Food & Dining",
            "taxonomy_subcategory": "Restaurant",
            "vera_expense_category": VeraPovExpenseCategory.FOOD_DINING,
            "taxonomy_id": "test-123",
        }
        fos_payload = manual_tx_payload_to_fos(validated)
        assert "vera_expense_category" not in fos_payload
        assert fos_payload["taxonomy_id"] == "test-123"
        assert fos_payload["amount"] == 150


class TestMatchVeraToPlaid:
    def test_match_vera_income_to_plaid(self):
        category, subcategory = match_vera_income_to_plaid(VeraPovIncomeCategory.SALARY_WAGES)
        assert category == "Income"
        assert subcategory == "Wages"

    def test_match_vera_expense_to_plaid(self):
        category, subcategory = match_vera_expense_to_plaid(VeraPovExpenseCategory.FOOD_DINING)
        assert category == "Food & Dining"
        assert subcategory is not None

    def test_match_none_returns_none(self):
        category, subcategory = match_vera_income_to_plaid(None)
        assert category is None
        assert subcategory is None


class TestDeriveVeraCategories:
    def test_derive_vera_expense_from_plaid(self):
        vera_category = derive_vera_expense("Food & Dining", "Restaurant")
        assert vera_category == VeraPovExpenseCategory.FOOD_DINING

    def test_derive_vera_income_from_plaid(self):
        vera_category = derive_vera_income("Income", "Wages")
        assert vera_category == VeraPovIncomeCategory.SALARY_WAGES

    def test_derive_expense_with_invalid_category_returns_none(self):
        vera_category = derive_vera_expense("Invalid Category", "Invalid Subcategory")
        assert vera_category is None


class TestChooseFromTaxonomy:
    def test_choose_exact_match(self):
        taxonomy = [
            {
                "id": "123",
                "primary": "Food & Dining",
                "primary_display": "Food & Dining",
                "detailed": "Restaurant",
                "detailed_display": "Restaurant",
            }
        ]
        category, subcategory, tax_id = choose_from_taxonomy(
            taxonomy, "Food & Dining", "Restaurant"
        )
        assert category == "Food & Dining"
        assert subcategory == "Restaurant"
        assert tax_id == "123"

    def test_choose_with_empty_taxonomy(self):
        category, subcategory, tax_id = choose_from_taxonomy([], "Food & Dining", "Restaurant")
        assert category is None
        assert subcategory is None
        assert tax_id is None

    def test_choose_with_case_insensitive_match(self):
        taxonomy = [
            {
                "id": "123",
                "primary": "Food & Dining",
                "primary_display": "Food & Dining",
                "detailed": "Restaurant",
                "detailed_display": "Restaurant",
            }
        ]
        category, subcategory, tax_id = choose_from_taxonomy(
            taxonomy, "food & dining", "restaurant"
        )
        assert tax_id == "123"


class TestBuildConfirmationSummary:
    def test_asset_summary(self):
        draft = {
            "entity_kind": "asset",
            "name": "House",
            "estimated_value": "500000",
            "currency_code": "USD",
        }
        summary = build_confirmation_summary(draft)
        assert "House" in summary
        assert "500000" in summary
        assert "USD" in summary

    def test_liability_summary(self):
        draft = {
            "entity_kind": "liability",
            "name": "Mortgage",
            "principal_balance": "300000",
            "currency_code": "USD",
        }
        summary = build_confirmation_summary(draft)
        assert "Mortgage" in summary
        assert "300000" in summary

    def test_manual_tx_summary(self):
        draft = {
            "entity_kind": "manual_tx",
            "kind": "expense",
            "amount": "150",
            "merchant_or_payee": "Restaurant XYZ",
        }
        summary = build_confirmation_summary(draft)
        assert "150" in summary
        assert "Restaurant XYZ" in summary


class TestToFOSCategory:
    def test_real_estate_conversion(self):
        assert to_fos_category(AssetCategory.REAL_ESTATE) == "real_estate"

    def test_electronics_equipment_conversion(self):
        assert to_fos_category(AssetCategory.ELECTRONICS_EQUIPMENT) == "electronics_equipment"

    def test_vehicles_conversion(self):
        assert to_fos_category(AssetCategory.VEHICLES) == "vehicles"

    def test_string_input(self):
        assert to_fos_category("Real Estate") == "real_estate"

    def test_ampersand_handling(self):
        result = to_fos_category("Electronics & Equipment")
        assert "&" not in result
        assert result == "electronics_equipment"
