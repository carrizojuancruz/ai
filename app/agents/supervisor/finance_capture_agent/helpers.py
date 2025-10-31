from __future__ import annotations

from decimal import Decimal
from typing import Any

from .constants import (
    VERA_EXPENSE_TO_PLAID_SUBCATEGORIES,
    VERA_INCOME_TO_PLAID_SUBCATEGORIES,
    AssetCategory,
    LiabilityCategory,
    VeraPovExpenseCategory,
    VeraPovIncomeCategory,
    to_fos_category,
)
from .schemas import ManualTransactionKind, NovaMicroIntentResult


def seed_draft_from_intent(intent: NovaMicroIntentResult) -> dict[str, Any]:
    draft: dict[str, Any] = {}
    kind = intent.kind
    if kind == "asset":
        draft["entity_kind"] = "asset"
        draft["name"] = intent.name or ""
        draft["estimated_value"] = to_decimal_str(intent.amount)
        draft["currency_code"] = (intent.currency_code or "").upper() or None
        draft["vera_category"] = intent.suggested_category or None
    elif kind == "liability":
        draft["entity_kind"] = "liability"
        draft["name"] = intent.name or ""
        draft["principal_balance"] = to_decimal_str(intent.amount)
        draft["currency_code"] = (intent.currency_code or "").upper() or None
        draft["vera_category"] = intent.suggested_category or None
    elif kind == "manual_tx":
        draft["entity_kind"] = "manual_tx"
        draft["amount"] = to_decimal_str(intent.amount)
        draft["currency_code"] = (intent.currency_code or "").upper() or None
        draft["merchant_or_payee"] = intent.merchant_or_payee or None
        draft["notes"] = intent.notes or None
        draft["taxonomy_category"] = intent.suggested_plaid_category or None
        draft["taxonomy_subcategory"] = intent.suggested_plaid_subcategory or None
        if intent.suggested_vera_income_category is not None:
            draft["vera_income_category"] = intent.suggested_vera_income_category
        if intent.suggested_vera_expense_category is not None:
            draft["vera_expense_category"] = intent.suggested_vera_expense_category
    return draft


def choose_from_taxonomy(categories: list[dict[str, Any]], cat: str | None, subcat: str | None) -> tuple[str | None, str | None, str | None]:
    """Choose category/subcategory from taxonomy and return taxonomy_id if available.

    The taxonomy comes in flat format from FOS API:
    - Each item has: id, primary, primary_display, detailed, detailed_display
    - We match against primary_display (category) and detailed_display (subcategory)

    Returns:
        Tuple of (category_name, subcategory_name, taxonomy_id)

    """
    if not categories:
        return None, None, None

    if cat and subcat:
        for item in categories:
            primary_display = str(item.get("primary_display") or "").strip().lower()
            detailed_display = str(item.get("detailed_display") or "").strip().lower()
            cat_lower = str(cat).strip().lower()
            subcat_lower = str(subcat).strip().lower()

            if primary_display == cat_lower and detailed_display == subcat_lower:
                taxonomy_id = item.get("id")
                return item.get("primary_display"), item.get("detailed_display"), taxonomy_id

    if cat:
        for item in categories:
            primary_display = str(item.get("primary_display") or "").strip().lower()
            cat_lower = str(cat).strip().lower()

            if primary_display == cat_lower:
                taxonomy_id = item.get("id")
                detailed_display = item.get("detailed_display")
                return item.get("primary_display"), detailed_display, taxonomy_id

    if categories:
        first_item = categories[0]
        taxonomy_id = first_item.get("id")
        return first_item.get("primary_display"), first_item.get("detailed_display"), taxonomy_id

    return None, None, None


def derive_vera_income(category: str, subcategory: str | None) -> VeraPovIncomeCategory | None:
    for vera, plaid_map in VERA_INCOME_TO_PLAID_SUBCATEGORIES.items():
        for plaid_cat, subcats in plaid_map.items():
            if plaid_cat == category and ((subcategory in subcats) if subcategory else True):
                return vera
    return None


def derive_vera_expense(category: str, subcategory: str | None) -> VeraPovExpenseCategory | None:
    for vera, plaid_map in VERA_EXPENSE_TO_PLAID_SUBCATEGORIES.items():
        for plaid_cat, subcats in plaid_map.items():
            if plaid_cat == category and ((subcategory in subcats) if subcategory else True):
                return vera
    return None


def normalize_basic_fields(draft: dict[str, Any]) -> None:
    code = draft.get("currency_code")
    if isinstance(code, str):
        draft["currency_code"] = code.upper()
    for key in ("estimated_value", "principal_balance", "minimum_payment_amount", "amount"):
        if draft.get(key) is not None:
            draft[key] = to_decimal_str(draft[key])


def asset_payload_from_draft(draft: dict[str, Any]) -> dict[str, Any]:
    """Build Pydantic validation payload from draft (uses Vera categories)."""
    vera_category = draft.get("vera_category") or AssetCategory.OTHER_ASSETS

    return {
        "name": draft.get("name") or "",
        "estimated_value": float(Decimal(str(draft.get("estimated_value") or "0"))),
        "currency_code": draft.get("currency_code") or "USD",
        "vera_category": vera_category,
        "is_active": True,
    }


def liability_payload_from_draft(draft: dict[str, Any]) -> dict[str, Any]:
    """Build Pydantic validation payload from draft (uses Vera categories)."""
    vera_category = draft.get("vera_category") or LiabilityCategory.OTHER_LIABILITIES

    return {
        "name": draft.get("name") or "",
        "principal_balance": float(Decimal(str(draft.get("principal_balance") or "0"))),
        "minimum_payment_amount": (float(Decimal(str(draft.get("minimum_payment_amount")))) if draft.get("minimum_payment_amount") is not None else None),
        "next_payment_due_date": draft.get("next_payment_due_date"),
        "currency_code": draft.get("currency_code") or "USD",
        "vera_category": vera_category,
        "is_active": True,
    }


def manual_tx_payload_from_draft(draft: dict[str, Any]) -> dict[str, Any]:
    """Build Pydantic validation payload from draft (uses Vera categories)."""
    kind = ManualTransactionKind.INCOME if (draft.get("kind") == "income") else ManualTransactionKind.EXPENSE
    payload = {
        "kind": kind,
        "amount": Decimal(str(draft.get("amount") or "0")),
        "currency_code": draft.get("currency_code") or "USD",
        "merchant_or_payee": draft.get("merchant_or_payee") or "",
        "taxonomy_category": draft.get("taxonomy_category") or ("Income" if kind == ManualTransactionKind.INCOME else "Food & Dining"),
        "taxonomy_subcategory": draft.get("taxonomy_subcategory") or "Other",
        "vera_income_category": draft.get("vera_income_category"),
        "vera_expense_category": draft.get("vera_expense_category"),
        "notes": draft.get("notes"),
        "recurring": draft.get("recurring"),
        "frequency": draft.get("frequency"),
        "taxonomy_id": draft.get("taxonomy_id"),
    }
    return payload


def manual_tx_payload_to_fos(validated: dict[str, Any]) -> dict[str, Any]:
    """Convert validated manual transaction payload to FOS API format.

    FOS API only accepts: amount, name, taxonomy_id
    """
    taxonomy_id = validated.get("taxonomy_id")
    if not taxonomy_id:
        raise ValueError("taxonomy_id is required for manual transactions")

    return {
        "amount": float(validated.get("amount") or 0),
        "name": validated.get("merchant_or_payee") or validated.get("name") or "",
        "taxonomy_id": taxonomy_id,
    }


def asset_payload_to_fos(validated: dict[str, Any]) -> dict[str, Any]:
    """Convert validated asset payload to FOS API format.

    Converts Vera categories to FOS snake_case format for persistence.
    """
    vera_category = validated.get("vera_category")
    if not vera_category:
        raise ValueError("vera_category is required for assets")
    return {
        "name": validated.get("name"),
        "category": to_fos_category(vera_category),
        "estimated_value": validated.get("estimated_value"),
        "currency_code": validated.get("currency_code"),
        "is_active": validated.get("is_active", True),
    }


def liability_payload_to_fos(validated: dict[str, Any]) -> dict[str, Any]:
    """Convert validated liability payload to FOS API format.

    Converts Vera categories to FOS snake_case format for persistence.
    """
    vera_category = validated.get("vera_category")
    if not vera_category:
        raise ValueError("vera_category is required for liabilities")
    return {
        "name": validated.get("name"),
        "category": to_fos_category(vera_category),
        "principal_balance": validated.get("principal_balance"),
        "minimum_payment_amount": validated.get("minimum_payment_amount"),
        "next_payment_due_date": validated.get("next_payment_due_date"),
        "currency_code": validated.get("currency_code"),
        "is_active": validated.get("is_active", True),
    }


def build_confirmation_summary(draft: dict[str, Any]) -> str:
    if not isinstance(draft, dict) or not draft:
        return "I have a draft ready. Please review and confirm to save."
    entity_kind = draft.get("entity_kind") or draft.get("kind")
    if entity_kind == "asset":
        return f"Confirm Asset: {draft.get('name')} — {draft.get('vera_category')} — {draft.get('estimated_value')} {draft.get('currency_code')}"
    if entity_kind == "liability":
        return f"Confirm Liability: {draft.get('name')} — {draft.get('vera_category')} — balance {draft.get('principal_balance')} {draft.get('currency_code')}"
    category = draft.get("taxonomy_category")
    subcat = draft.get("taxonomy_subcategory")
    pov = draft.get("vera_income_category") or draft.get("vera_expense_category")
    return (
        f"Confirm Transaction: {draft.get('amount')} {draft.get('currency_code')}\n"
        f"Merchant/Payee: {draft.get('merchant_or_payee')}\n"
        f"Category: {category} › {subcat} (Vera: {pov})"
    )


def extract_id_from_response(body: dict[str, Any] | None) -> Any:
    if not body:
        return None
    for key in ("id", "asset_id", "liability_id", "transaction_id", "uuid"):
        if key in body:
            return body[key]
    return None


def to_decimal_str(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return str(Decimal(str(value)))
    except Exception:
        return None
