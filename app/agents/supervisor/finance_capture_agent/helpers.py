from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .constants import (
    CATEGORY_VARIANTS,
    SUBCATEGORY_VARIANTS,
    VERA_EXPENSE_TO_PLAID_SUBCATEGORIES,
    VERA_INCOME_TO_PLAID_SUBCATEGORIES,
    AssetCategory,
    LiabilityCategory,
    VeraPovExpenseCategory,
    VeraPovIncomeCategory,
    to_fos_category,
)
from .schemas import ManualTransactionKind, NovaMicroIntentResult

logger = logging.getLogger(__name__)
_ALIAS_KEY_PATTERN = re.compile(r"[^a-z0-9]")


def _alias_key(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _ALIAS_KEY_PATTERN.sub("", value.lower())
    return normalized or None


def _build_lookup(source: dict[str, tuple[str, ...]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for canonical, variants in source.items():
        keys = (canonical,) + variants
        for name in keys:
            key = _alias_key(name)
            if key:
                lookup[key] = canonical
    return lookup


_CATEGORY_LOOKUP = _build_lookup(CATEGORY_VARIANTS)
_SUBCATEGORY_LOOKUP = _build_lookup(SUBCATEGORY_VARIANTS)


def _normalize_category(value: str | None) -> str | None:
    if value is None:
        return None
    key = _alias_key(value)
    if key is None:
        return value.strip() or None
    return _CATEGORY_LOOKUP.get(key) or (value.strip() or None)


def _normalize_subcategory(value: str | None) -> str | None:
    if value is None:
        return None
    key = _alias_key(value)
    if key is None:
        return value.strip() or None
    return _SUBCATEGORY_LOOKUP.get(key) or (value.strip() or None)


@dataclass(frozen=True)
class _TaxonomyRow:
    category_key: str | None
    subcategory_key: str | None
    category_display: str
    subcategory_display: str
    taxonomy_id: str | None

    @classmethod
    def from_raw(cls, item: dict[str, Any]) -> "_TaxonomyRow":
        primary_display = str(item.get("primary_display") or item.get("primary") or "").strip()
        detailed_display = str(item.get("detailed_display") or item.get("detailed") or "").strip()
        category = _normalize_category(primary_display)
        subcategory = _normalize_subcategory(detailed_display)
        return cls(
            category_key=_alias_key(category),
            subcategory_key=_alias_key(subcategory),
            category_display=category or primary_display,
            subcategory_display=subcategory or detailed_display,
            taxonomy_id=item.get("id"),
        )


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


def choose_from_taxonomy(
    categories: list[dict[str, Any]], cat: str | None, subcat: str | None
) -> tuple[str | None, str | None, str | None]:
    """Choose category/subcategory from taxonomy and return taxonomy_id if available.

    The taxonomy comes in flat format from FOS API:
    - Each item has: id, primary, primary_display, detailed, detailed_display
    - We match against primary_display (category) and detailed_display (subcategory)

    Returns:
        Tuple of (category_name, subcategory_name, taxonomy_id)

    """
    if not categories:
        logger.warning("[choose_from_taxonomy] no categories provided")
        return None, None, None

    rows = [_TaxonomyRow.from_raw(item) for item in categories]

    cat_normalized = _normalize_category(cat)
    subcat_normalized = _normalize_subcategory(subcat)
    if cat_normalized and cat_normalized.strip().lower() == "income" and not subcat_normalized:
        subcat_normalized = "Other income"
    cat_key = _alias_key(cat_normalized)
    subcat_key = _alias_key(subcat_normalized)

    if cat_key and subcat_key:
        for row in rows:
            if row.category_key == cat_key and row.subcategory_key == subcat_key:
                return row.category_display, row.subcategory_display, row.taxonomy_id

    if subcat_key:
        for row in rows:
            if row.subcategory_key == subcat_key:
                return row.category_display, row.subcategory_display, row.taxonomy_id

    if cat_key:
        for row in rows:
            if row.category_key == cat_key:
                return row.category_display, row.subcategory_display, row.taxonomy_id

    logger.debug(
        "[choose_from_taxonomy] no taxonomy match for category=%r subcategory=%r (will use as-is)",
        cat,
        subcat,
    )
    return None, None, None


def derive_vera_income(category: str, subcategory: str | None) -> VeraPovIncomeCategory | None:
    canonical_category = _normalize_category(category) or category
    canonical_subcategory = _normalize_subcategory(subcategory) or subcategory
    category_normalized = str(canonical_category).strip().lower() if canonical_category else ""
    subcategory_normalized = str(canonical_subcategory).strip().lower() if canonical_subcategory else None
    for vera, plaid_map in VERA_INCOME_TO_PLAID_SUBCATEGORIES.items():
        for plaid_cat, subcats in plaid_map.items():
            plaid_cat_normalized = str(plaid_cat).strip().lower()
            subcats_normalized = [str(s).strip().lower() for s in subcats]
            if plaid_cat_normalized == category_normalized and (
                (subcategory_normalized in subcats_normalized) if subcategory_normalized else True
            ):
                return vera
    logger.warning("[derive_vera_income] no match found for category=%r subcategory=%r", category, subcategory)
    return None


def derive_vera_expense(category: str, subcategory: str | None) -> VeraPovExpenseCategory | None:
    canonical_category = _normalize_category(category) or category
    canonical_subcategory = _normalize_subcategory(subcategory) or subcategory
    category_normalized = str(canonical_category).strip().lower() if canonical_category else ""
    subcategory_normalized = str(canonical_subcategory).strip().lower() if canonical_subcategory else None
    for vera, plaid_map in VERA_EXPENSE_TO_PLAID_SUBCATEGORIES.items():
        for plaid_cat, subcats in plaid_map.items():
            plaid_cat_normalized = str(plaid_cat).strip().lower()
            subcats_normalized = [str(s).strip().lower() for s in subcats]
            if plaid_cat_normalized == category_normalized and (
                (subcategory_normalized in subcats_normalized) if subcategory_normalized else True
            ):
                return vera
    logger.warning("[derive_vera_expense] no match found for category=%r subcategory=%r", category, subcategory)
    return None


def _match_vera_to_plaid(
    vera_value: VeraPovIncomeCategory | VeraPovExpenseCategory | str | None,
    mapping: dict[VeraPovIncomeCategory | VeraPovExpenseCategory, dict[str, tuple[str, ...]]],
) -> tuple[str | None, str | None]:
    if vera_value is None:
        return None, None

    if isinstance(vera_value, (VeraPovIncomeCategory, VeraPovExpenseCategory)):
        target = vera_value.value.strip().lower()
    else:
        target = str(vera_value).strip().lower()

    if not target:
        return None, None

    for vera_category, plaid_map in mapping.items():
        if vera_category.value.strip().lower() != target:
            continue
        for plaid_category, subcats in plaid_map.items():
            if subcats:
                return plaid_category, subcats[0]
            return plaid_category, None

    return None, None


def match_vera_income_to_plaid(
    vera_income: VeraPovIncomeCategory | str | None,
) -> tuple[str | None, str | None]:
    """Map a Vera income POV category back to a Plaid category/subcategory pair."""
    return _match_vera_to_plaid(vera_income, VERA_INCOME_TO_PLAID_SUBCATEGORIES)


def match_vera_expense_to_plaid(
    vera_expense: VeraPovExpenseCategory | str | None,
) -> tuple[str | None, str | None]:
    """Map a Vera expense POV category back to a Plaid category/subcategory pair."""
    return _match_vera_to_plaid(vera_expense, VERA_EXPENSE_TO_PLAID_SUBCATEGORIES)


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
        "minimum_payment_amount": (
            float(Decimal(str(draft.get("minimum_payment_amount"))))
            if draft.get("minimum_payment_amount") is not None
            else None
        ),
        "next_payment_due_date": draft.get("next_payment_due_date"),
        "currency_code": draft.get("currency_code") or "USD",
        "vera_category": vera_category,
        "is_active": True,
    }


def manual_tx_payload_from_draft(draft: dict[str, Any]) -> dict[str, Any]:
    """Build Pydantic validation payload from draft (uses Vera categories)."""
    kind = ManualTransactionKind.INCOME if (draft.get("kind") == "income") else ManualTransactionKind.EXPENSE

    # Convert enum values to their string values for Pydantic
    vera_income = draft.get("vera_income_category")
    vera_expense = draft.get("vera_expense_category")
    if isinstance(vera_income, VeraPovIncomeCategory):
        vera_income = vera_income.value
    if isinstance(vera_expense, VeraPovExpenseCategory):
        vera_expense = vera_expense.value
    raw_name = draft.get("name")
    raw_merchant = draft.get("merchant_or_payee")
    raw_notes = draft.get("notes")

    def _clean(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    merchant = _clean(raw_merchant) or _clean(raw_name) or _clean(raw_notes)
    if not merchant:
        merchant = "Manual income" if kind == ManualTransactionKind.INCOME else "Manual expense"

    name_value = _clean(raw_name) or merchant

    payload = {
        "kind": kind,
        "amount": Decimal(str(draft.get("amount") or "0")),
        "currency_code": draft.get("currency_code") or "USD",
        "name": name_value,
        "merchant_or_payee": merchant,
        "taxonomy_category": draft.get("taxonomy_category")
        or ("Income" if kind == ManualTransactionKind.INCOME else "Food & Dining"),
        "taxonomy_subcategory": draft.get("taxonomy_subcategory") or "Other",
        "vera_income_category": vera_income,
        "vera_expense_category": vera_expense,
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

def safe_normalize_string(value: str | None) -> str | None:
    """Safely normalize a string by stripping whitespace and converting to lowercase.

    Returns None if value is None or empty after normalization.
    """
    if value is None:
        return None
    normalized = str(value).strip().lower()
    return normalized if normalized else None


def safe_str_equal(str1: str | None, str2: str | None) -> bool:
    """Safely compare two strings case-insensitively with whitespace trimming.

    Handles None values gracefully.
    """
    if str1 is None or str2 is None:
        return str1 is str2  # Both None
    return safe_normalize_string(str1) == safe_normalize_string(str2)
