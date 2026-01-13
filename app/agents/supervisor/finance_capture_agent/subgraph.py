from __future__ import annotations

import contextlib
import logging
import uuid
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import interrupt

from app.core.app_state import get_sse_queue
from app.services.memory.checkpointer import KVRedisCheckpointer
from app.utils.tools import get_config_value

from .constants import AssetCategory, LiabilityCategory
from .helpers import (
    asset_payload_from_draft,
    asset_payload_to_fos,
    build_confirmation_summary,
    choose_from_taxonomy,
    derive_vera_expense,
    derive_vera_income,
    extract_id_from_response,
    liability_payload_from_draft,
    liability_payload_to_fos,
    manual_tx_payload_from_draft,
    manual_tx_payload_to_fos,
    match_vera_expense_to_plaid,
    match_vera_income_to_plaid,
    normalize_basic_fields,
    safe_str_equal,
    seed_draft_from_intent,
)
from .nova import extract_intents
from .schemas import AssetCreate, LiabilityCreate, ManualTransactionCreate, NovaMicroIntentResult
from .tools import get_taxonomy, persist_asset, persist_liability, persist_manual_transaction


class CaptureConfirmationItem(TypedDict, total=False):
    item_id: str
    summary: str
    draft: dict[str, Any]
    validated: dict[str, Any] | None
    entity_kind: str | None
    was_edited: bool | None
    persisted_ids: list[str] | None


DecisionLiteral = Literal["approve", "edit", "cancel"]


class CaptureDecisionPayload(TypedDict, total=False):
    decision: DecisionLiteral
    draft: dict[str, Any] | None


class FinanceCaptureState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    intent: dict[str, Any] | None
    capture_draft: dict[str, Any] | None
    taxonomy: dict[str, Any] | None
    validated: dict[str, Any] | None
    confirm_decision: str | None
    persisted_ids: list[str] | None
    confirm_id: str | None
    from_edit: bool | None
    completion_context: dict[str, Any] | None
    completion_contexts: list[dict[str, Any]] | None
    active_item_id: str | None
    pending_confirmation_items: list[CaptureConfirmationItem] | None
    confirmation_decisions: dict[str, CaptureDecisionPayload] | None
    intent_queue: list[dict[str, Any]] | None


def _generate_item_id(state: FinanceCaptureState, *, force_new: bool = False) -> str:
    active_id = state.get("active_item_id")
    if not force_new and isinstance(active_id, str) and active_id:
        return active_id
    return str(uuid.uuid4())


def _upsert_confirmation_item(
    *,
    state: FinanceCaptureState,
    item_id: str,
    draft: dict[str, Any],
    validated: dict[str, Any] | None,
    entity_kind: str | None,
    summary: str,
    was_edited: bool,
) -> list[CaptureConfirmationItem]:
    existing = list(state.get("pending_confirmation_items") or [])
    filtered = [item for item in existing if item.get("item_id") != item_id]
    filtered.append(
        {
            "item_id": item_id,
            "draft": draft,
            "validated": validated,
            "entity_kind": entity_kind,
            "summary": summary,
            "was_edited": was_edited,
        }
    )
    return filtered


def _serialize_confirmation_items(items: list[CaptureConfirmationItem]) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for item in items:
        draft = item.get("validated") or item.get("draft") or {}
        serialized.append(
            {
                "item_id": item.get("item_id"),
                "summary": item.get("summary") or build_confirmation_summary(draft),
                "draft": draft,
            }
        )
    return serialized


def _coerce_single_decision(decision: Any) -> tuple[DecisionLiteral, dict[str, Any] | None]:
    decision_str: DecisionLiteral = "approve"
    draft_patch: dict[str, Any] | None = None

    if isinstance(decision, dict) and "decisions" in decision:
        raise ValueError("Expected single decision payload without 'decisions' key")

    if isinstance(decision, dict):
        maybe_draft = decision.get("draft")
        if isinstance(maybe_draft, dict) and maybe_draft:
            draft_patch = maybe_draft
            action = str(decision.get("action") or "edit").lower()
            decision_str = "edit" if action not in ("cancel", "reject", "no", "false") else "cancel"
        elif "approved" in decision:
            decision_str = "approve" if decision.get("approved") else "cancel"
        else:
            action = str(decision.get("action") or "approve").lower()
            if action in ("approve", "approved", "yes", "true"):
                decision_str = "approve"
            elif action in ("cancel", "reject", "no", "false"):
                decision_str = "cancel"
            elif action in ("edit", "update"):
                decision_str = "edit"
    elif isinstance(decision, bool):
        decision_str = "approve" if decision else "cancel"
    elif isinstance(decision, str):
        action = decision.lower()
        if action in ("approve", "approved", "yes", "true"):
            decision_str = "approve"
        elif action in ("cancel", "reject", "no", "false"):
            decision_str = "cancel"

    return decision_str, draft_patch


def _as_decision_literal(value: str) -> DecisionLiteral:
    if value == "cancel":
        return "cancel"
    if value == "edit":
        return "edit"
    return "approve"


def normalize_confirmation_decisions(
    decision_payload: Any,
    items: list[CaptureConfirmationItem],
) -> dict[str, CaptureDecisionPayload]:
    normalized: dict[str, CaptureDecisionPayload] = {}
    if isinstance(decision_payload, dict) and isinstance(decision_payload.get("decisions"), list):
        for entry in decision_payload["decisions"]:
            if not isinstance(entry, dict):
                continue
            item_id = entry.get("item_id")
            if not item_id:
                continue
            decision_value = entry.get("decision") or entry.get("action") or entry.get("status") or "approve"
            decision = str(decision_value).lower()
            if decision in ("yes", "true", "approved"):
                decision_literal = "approve"
            elif decision in ("no", "false", "rejected", "cancelled", "cancel"):
                decision_literal = "cancel"
            elif decision in ("edit", "update"):
                decision_literal = "edit"
            else:
                decision_literal = "approve"
            draft_patch = entry.get("draft")
            normalized[item_id] = {
                "decision": decision_literal,
                "draft": draft_patch if isinstance(draft_patch, dict) else None,
            }
        if normalized:
            return normalized

    decision_str, draft_patch = _coerce_single_decision(decision_payload)
    for item in items:
        item_id = item.get("item_id")
        if not item_id:
            continue
        normalized[item_id] = {
            "decision": _as_decision_literal(decision_str),
            "draft": draft_patch,
        }
    return normalized


def _validate_draft_payload(
    *,
    draft: dict[str, Any],
    intent_dict: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str]:
    working_draft = dict(draft)
    normalize_basic_fields(working_draft)
    kind = str((intent_dict or {}).get("kind") or working_draft.get("entity_kind") or "").strip()

    if kind == "asset":
        payload = AssetCreate(**asset_payload_from_draft(working_draft)).model_dump(mode="json")
        payload["entity_kind"] = "asset"
        return payload, "asset"
    if kind == "liability":
        payload = LiabilityCreate(**liability_payload_from_draft(working_draft)).model_dump(mode="json")
        payload["entity_kind"] = "liability"
        return payload, "liability"
    if kind == "manual_tx":
        payload_dict = manual_tx_payload_from_draft(working_draft)
        payload = ManualTransactionCreate(**payload_dict).model_dump(mode="json")
        payload["entity_kind"] = working_draft.get("entity_kind") or working_draft.get("kind") or "manual_tx"
        return payload, payload["entity_kind"]

    raise ValueError(f"Unsupported entity kind: {kind or 'unknown'}")


def _build_completion_message(
    *,
    entity_kind: str | None,
    draft: dict[str, Any],
    confirm_decision: DecisionLiteral | str,
    persisted_ids: list[str] | None,
    was_edited: bool,
    error: str | None = None,
) -> str:
    entity_kind_normalized = (entity_kind or draft.get("entity_kind") or draft.get("kind") or "").lower()
    if error:
        return f"Task failed: {error}"
    if confirm_decision == "cancel":
        if entity_kind_normalized == "asset":
            name = draft.get("name", "asset")
            return f"Task cancelled: Asset '{name}' was not saved."
        if entity_kind_normalized == "liability":
            name = draft.get("name", "liability")
            return f"Task cancelled: Liability '{name}' was not saved."
        if entity_kind_normalized in ("income", "expense", "manual_tx"):
            merchant = draft.get("merchant_or_payee", "transaction")
            label = "Income" if entity_kind_normalized == "income" else "Expense"
            return f"Task cancelled: {label} transaction for {merchant} was not saved."
        return "Task cancelled: No changes were saved."

    if persisted_ids:
        if entity_kind_normalized == "asset":
            name = draft.get("name", "asset")
            value = draft.get("estimated_value", "")
            currency = draft.get("currency_code", "USD")
            edit_note = " Note: The user edited the original values before saving." if was_edited else ""
            return f"TASK COMPLETED: Asset '{name}' worth {value} {currency} has been successfully saved to the user's financial profile.{edit_note} No further action needed."
        if entity_kind_normalized == "liability":
            name = draft.get("name", "liability")
            balance = draft.get("principal_balance", "")
            currency = draft.get("currency_code", "USD")
            edit_note = " Note: The user edited the original values before saving." if was_edited else ""
            return f"TASK COMPLETED: Liability '{name}' with balance {balance} {currency} has been successfully saved to the user's financial profile.{edit_note} No further action needed."
        if entity_kind_normalized in ("income", "expense", "manual_tx"):
            kind_label = "Income" if entity_kind_normalized == "income" else "Expense"
            amount = draft.get("amount", "")
            currency = draft.get("currency_code", "USD")
            merchant = draft.get("merchant_or_payee", "transaction")
            edit_note = " Note: The user edited the original values before saving." if was_edited else ""
            return f"TASK COMPLETED: {kind_label} transaction for {merchant} ({amount} {currency}) has been successfully saved.{edit_note} No further action needed."

    return "Finance data capture task completed."


def create_finance_capture_graph(
    checkpointer: KVRedisCheckpointer,
):
    logger = logging.getLogger(__name__)

    async def _maybe_recompute_manual_tx_taxonomy(
        *,
        draft: dict[str, Any],
        patch: dict[str, Any] | None,
    ) -> dict[str, Any]:
        base_kind = str(draft.get("entity_kind") or draft.get("kind") or "").strip().lower()
        if base_kind not in ("manual_tx", "income", "expense"):
            return draft

        patch = patch or {}
        if not any(key in patch for key in ("vera_income_category", "vera_expense_category", "kind")):
            return draft

        effective_kind: str | None = None

        patch_kind_raw = patch.get("kind")
        if isinstance(patch_kind_raw, str):
            patch_kind = patch_kind_raw.strip().lower()
            if patch_kind in ("income", "expense"):
                effective_kind = patch_kind

        if effective_kind is None:
            if "vera_income_category" in patch and patch.get("vera_income_category") is not None:
                effective_kind = "income"
            elif "vera_expense_category" in patch and patch.get("vera_expense_category") is not None:
                effective_kind = "expense"


        if effective_kind is None:
            kind_existing = str(draft.get("kind") or "").strip().lower()
            if kind_existing in ("income", "expense"):
                effective_kind = kind_existing
            elif draft.get("vera_income_category"):
                effective_kind = "income"
                draft["kind"] = "income"
            elif draft.get("vera_expense_category"):
                effective_kind = "expense"
                draft["kind"] = "expense"
            else:
                return draft

        existing_kind = str(draft.get("kind") or "").strip().lower()
        if existing_kind not in ("income", "expense"):
            existing_kind = None
        if (
            patch.get("vera_income_category") == draft.get("vera_income_category")
            and patch.get("vera_expense_category") == draft.get("vera_expense_category")
            and effective_kind == existing_kind
        ):
            return draft

        kind = effective_kind
        if isinstance(patch_kind_raw, str):
            draft["kind"] = kind

        if kind == "income":
            draft["vera_expense_category"] = None
        elif kind == "expense":
            draft["vera_income_category"] = None

        scope: Literal["income", "expenses"] = "income" if kind == "income" else "expenses"

        vera_value: Any
        if kind == "income":
            vera_value = patch.get("vera_income_category", draft.get("vera_income_category"))
            plaid_category, plaid_subcategory = match_vera_income_to_plaid(vera_value)
        else:
            vera_value = patch.get("vera_expense_category", draft.get("vera_expense_category"))
            plaid_category, plaid_subcategory = match_vera_expense_to_plaid(vera_value)

        if not plaid_category:
            logger.warning(
                "[finance_capture] manual_tx.recompute_taxonomy.no_plaid_match vera=%r kind=%s",
                vera_value,
                kind,
            )
            return draft

        try:
            taxonomy_result = await get_taxonomy(scope)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "[finance_capture] manual_tx.recompute_taxonomy.taxonomy_fetch_failed scope=%s error=%s",
                scope,
                exc,
            )
            return draft

        taxonomy = taxonomy_result.model_dump()
        categories = taxonomy.get("categories") or []
        chosen_category, chosen_subcategory, taxonomy_id = choose_from_taxonomy(
            categories,
            plaid_category,
            plaid_subcategory,
        )

        if not taxonomy_id:
            logger.warning(
                "[finance_capture] manual_tx.recompute_taxonomy.no_taxonomy_id vera=%r kind=%s plaid_cat=%r subcat=%r",
                vera_value,
                kind,
                plaid_category,
                plaid_subcategory,
            )
            return draft

        draft["taxonomy_category"] = chosen_category or plaid_category
        draft["taxonomy_subcategory"] = chosen_subcategory or plaid_subcategory
        draft["taxonomy_id"] = taxonomy_id
        return draft

    async def parse_and_normalize(state: FinanceCaptureState, config: RunnableConfig) -> dict[str, Any]:
        user_message = ""
        for message in reversed(state.get("messages", [])):
            role = getattr(message, "role", getattr(message, "type", None))
            if role in ("user", "human"):
                content = getattr(message, "content", None)
                if isinstance(content, str):
                    user_message = content.strip()
                    break

        intents: list[NovaMicroIntentResult] = []
        if user_message:
            intents = extract_intents(user_message)

        update: dict[str, Any] = {}
        if not intents:
            return update

        active_item_id = _generate_item_id(state, force_new=True)
        update["active_item_id"] = active_item_id
        primary_intent = intents[0]
        update["intent"] = primary_intent.model_dump()
        draft = seed_draft_from_intent(primary_intent)
        if draft:
            draft["item_id"] = active_item_id
        update["capture_draft"] = draft
        if len(intents) > 1:
            remaining = [intent.model_dump() for intent in intents[1:]]
            update["intent_queue"] = remaining

        return update

    async def fetch_taxonomy_if_needed(state: FinanceCaptureState, config: RunnableConfig) -> dict[str, Any]:
        intent_dict = state.get("intent") or {}
        kind = str(intent_dict.get("kind") or "")
        if kind != "manual_tx":
            return {}

        draft: dict[str, Any] = state.get("capture_draft") or {}
        suggested_category = draft.get("taxonomy_category") or intent_dict.get("suggested_plaid_category")

        scope = "expenses"
        if (
            draft.get("kind") == "income"
            or isinstance(suggested_category, str)
            and suggested_category.strip().lower() == "income"
            or draft.get("vera_income_category")
        ):
            scope = "income"

        try:
            taxonomy = await get_taxonomy(scope)  # HTTP call to FOS
        except Exception as exc:  # noqa: BLE001
            logger.error("[finance_capture] taxonomy_fetch_failed scope=%s error=%s", scope, exc)
            return {}

        return {"taxonomy": taxonomy.model_dump()}

    async def map_categories(state: FinanceCaptureState, config: RunnableConfig) -> dict[str, Any]:
        draft: dict[str, Any] = dict(state.get("capture_draft") or {})
        intent_dict = state.get("intent") or {}
        kind = str(intent_dict.get("kind") or draft.get("entity_kind") or "").strip()

        if not kind:
            return {}

        if kind in ("asset", "liability"):
            # Ensure provided category is an allowed enum; keep as Vera POV for UX
            category_raw = (draft.get("vera_category") or "").strip()
            if kind == "asset" and category_raw:
                with contextlib.suppress(Exception):
                    draft["vera_category"] = AssetCategory(category_raw)
            if kind == "liability" and category_raw:
                with contextlib.suppress(Exception):
                    draft["vera_category"] = LiabilityCategory(category_raw)
            return {"capture_draft": draft}

        # manual transaction: map Plaid category/subcategory and derive Vera POV
        if kind == "manual_tx":
            taxonomy = state.get("taxonomy") or {}
            if not taxonomy:
                logger.warning(
                    "[finance_capture] map_categories.manual_tx_requires_taxonomy active_item_id=%s",
                    state.get("active_item_id"),
                )
                return {}

            categories = taxonomy.get("categories") or []
            if not categories:
                logger.warning(
                    "[finance_capture] map_categories.taxonomy_has_no_categories active_item_id=%s",
                    state.get("active_item_id"),
                )
                return {}

            suggested_category = draft.get("taxonomy_category") or intent_dict.get("suggested_plaid_category")
            suggested_subcat = draft.get("taxonomy_subcategory") or intent_dict.get("suggested_plaid_subcategory")

            chosen_category, chosen_subcategory, taxonomy_id = choose_from_taxonomy(
                categories,
                suggested_category,
                suggested_subcat,
            )

            if not chosen_category or not chosen_subcategory or not taxonomy_id:
                logger.warning(
                    "[finance_capture] taxonomy lookup failed for Nova suggestion, attempting Vera-based fallback: "
                    "category=%r subcategory=%r",
                    suggested_category,
                    suggested_subcat,
                )

                vera_income = intent_dict.get("suggested_vera_income_category") or draft.get("vera_income_category")
                vera_expense = intent_dict.get("suggested_vera_expense_category") or draft.get("vera_expense_category")

                plaid_cat_fallback: str | None = None
                plaid_subcat_fallback: str | None = None

                if vera_income is not None:
                    plaid_cat_fallback, plaid_subcat_fallback = match_vera_income_to_plaid(vera_income)
                elif vera_expense is not None:
                    plaid_cat_fallback, plaid_subcat_fallback = match_vera_expense_to_plaid(vera_expense)

                if plaid_cat_fallback:
                    fb_category, fb_subcategory, fb_taxonomy_id = choose_from_taxonomy(
                        categories,
                        plaid_cat_fallback,
                        plaid_subcat_fallback,
                    )
                    if fb_taxonomy_id:
                        chosen_category = fb_category or plaid_cat_fallback
                        chosen_subcategory = fb_subcategory or plaid_subcat_fallback
                        taxonomy_id = fb_taxonomy_id

            if not chosen_category or not chosen_subcategory:
                logger.warning(
                    "[finance_capture] taxonomy lookup ultimately failed, using Nova's suggestion without taxonomy_id: "
                    "category=%r subcategory=%r",
                    suggested_category,
                    suggested_subcat,
                )
                chosen_category = suggested_category or ""
                chosen_subcategory = suggested_subcat or ""
                taxonomy_id = None

            draft["taxonomy_category"] = chosen_category or ""
            draft["taxonomy_subcategory"] = chosen_subcategory or ""
            draft["taxonomy_id"] = taxonomy_id

            # Derive Vera POV category (income vs expense)
            if chosen_category and safe_str_equal(chosen_category, "income"):
                draft["kind"] = "income"
                derived_income = derive_vera_income(chosen_category, chosen_subcategory)
                draft["vera_income_category"] = derived_income or draft.get("vera_income_category")
                draft["vera_expense_category"] = None
            else:
                draft["kind"] = "expense"
                derived_expense = derive_vera_expense(chosen_category, chosen_subcategory)
                draft["vera_expense_category"] = derived_expense or draft.get("vera_expense_category")
                draft["vera_income_category"] = None

            return {"capture_draft": draft}

        return {}

    async def load_next_intent(state: FinanceCaptureState, config: RunnableConfig) -> dict[str, Any]:
        queue = list(state.get("intent_queue") or [])
        if not queue:
            return {}

        next_intent_dict = queue.pop(0)
        try:
            next_intent = NovaMicroIntentResult.model_validate(next_intent_dict)
        except Exception:
            return {"intent_queue": queue or None}

        active_item_id = _generate_item_id(state, force_new=True)
        draft = seed_draft_from_intent(next_intent)
        if draft:
            draft["item_id"] = active_item_id

        update: dict[str, Any] = {
            "intent": next_intent.model_dump(),
            "capture_draft": draft,
            "active_item_id": active_item_id,
            "intent_queue": queue or None,
            "from_edit": None,
            "validated": None,
            "taxonomy": None,
        }
        return update

    async def validate_schema(state: FinanceCaptureState, config: RunnableConfig) -> dict[str, Any]:
        draft: dict[str, Any] = dict(state.get("capture_draft") or {})
        intent_dict = state.get("intent") or {}
        was_edit = state.get("confirm_decision") == "edit"

        try:
            payload, entity_kind = _validate_draft_payload(draft=draft, intent_dict=intent_dict)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[finance_capture] schema_validation_failed error=%s", exc)
            return {"messages": [{"role": "assistant", "content": "Could you confirm or provide the missing details?"}]}

        item_id = state.get("active_item_id") or draft.get("item_id") or _generate_item_id(state)
        summary = build_confirmation_summary(payload)
        pending_items = _upsert_confirmation_item(
            state=state,
            item_id=item_id,
            draft=draft,
            validated=payload,
            entity_kind=entity_kind,
            summary=summary,
            was_edited=was_edit,
        )

        result: dict[str, Any] = {
            "validated": payload,
            "pending_confirmation_items": pending_items,
            "active_item_id": item_id,
        }
        if was_edit:
            result["from_edit"] = True
        return result

    async def confirm_human(state: FinanceCaptureState, config: RunnableConfig) -> dict[str, Any]:
        items = state.get("pending_confirmation_items") or []
        if not items:
            fallback_draft: dict[str, Any] = state.get("validated") or state.get("capture_draft") or {}
            if fallback_draft:
                items = [
                    {
                        "item_id": state.get("active_item_id") or str(uuid.uuid4()),
                        "draft": fallback_draft,
                        "validated": state.get("validated"),
                        "summary": build_confirmation_summary(fallback_draft),
                        "entity_kind": fallback_draft.get("entity_kind"),
                        "was_edited": False,
                    }
                ]

        serialized_items = _serialize_confirmation_items(items)
        if not serialized_items:
            return {}

        confirm_id = get_config_value(config, "confirm_id")

        event_data = {"items": serialized_items, "confirm_id": confirm_id or str(uuid.uuid4())}
        if len(serialized_items) == 1:
            event_data["summary"] = serialized_items[0]["summary"]
            event_data["draft"] = serialized_items[0]["draft"]

        if not confirm_id:
            confirm_id = str(uuid.uuid4())
            event_data["confirm_id"] = confirm_id
            q = get_sse_queue(get_config_value(config, "thread_id"))
            await q.put({"event": "confirm.request", "data": event_data})

        decision_payload = interrupt({"event": "confirm.request", "data": event_data})

        decisions_map = normalize_confirmation_decisions(decision_payload, items)
        update: dict[str, Any] = {
            "confirmation_decisions": decisions_map,
            "confirm_id": confirm_id,
            "confirm_decision": None,
        }

        if len(decisions_map) == 1:
            update["confirm_decision"] = next(iter(decisions_map.values())).get("decision")

        return update

    async def persist(state: FinanceCaptureState, config: RunnableConfig) -> dict[str, Any]:
        user_id = get_config_value(config, "user_id")
        items = state.get("pending_confirmation_items") or []
        decisions = state.get("confirmation_decisions") or {}

        if not isinstance(user_id, str) or not user_id:
            logger.error("[finance_capture] missing_user_id_for_persist")
            return {
                "messages": [
                    {
                        "role": "assistant",
                        "content": "Cannot save right now. Missing user id.",
                        "name": "finance_capture_agent",
                    }
                ]
            }

        completion_contexts: list[dict[str, Any]] = []

        for item in items:
            item_id = item.get("item_id") or str(uuid.uuid4())
            decision_payload = decisions.get(item_id) or {"decision": "approve"}
            decision = _as_decision_literal(str(decision_payload.get("decision") or "approve"))
            draft = dict(item.get("draft") or {})
            patch = decision_payload.get("draft")
            if isinstance(patch, dict) and patch:
                draft = {**draft, **patch}

            draft = await _maybe_recompute_manual_tx_taxonomy(draft=draft, patch=patch)

            if decision == "cancel":
                completion_contexts.append(
                    {
                        "item_id": item_id,
                        "entity_kind": item.get("entity_kind") or draft.get("entity_kind"),
                        "confirm_decision": "cancel",
                        "persisted_ids": None,
                        "was_edited": item.get("was_edited", False),
                        "draft": draft,
                        "completion_message": _build_completion_message(
                            entity_kind=item.get("entity_kind"),
                            draft=draft,
                            confirm_decision="cancel",
                            persisted_ids=None,
                            was_edited=item.get("was_edited", False),
                            error=None,
                        ),
                    }
                )
                continue

            try:
                validated_payload, entity_kind = _validate_draft_payload(draft=draft, intent_dict=None)
            except Exception as exc:  # noqa: BLE001
                error_msg = f"Validation failed: {exc}"
                logger.warning("[finance_capture] multi_item.validation_failed item=%s error=%s", item_id, exc)
                completion_contexts.append(
                    {
                        "item_id": item_id,
                        "entity_kind": draft.get("entity_kind"),
                        "confirm_decision": "error",
                        "persisted_ids": None,
                        "was_edited": True,
                        "draft": draft,
                        "error": error_msg,
                        "completion_message": _build_completion_message(
                            entity_kind=draft.get("entity_kind"),
                            draft=draft,
                            confirm_decision="approve",
                            persisted_ids=None,
                            was_edited=True,
                            error=error_msg,
                        ),
                    }
                )
                continue

            persisted_ids: list[str] = []
            try:
                if entity_kind in ("income", "expense", "manual_tx"):
                    fos_payload = manual_tx_payload_to_fos(validated_payload)
                    resp = await persist_manual_transaction(user_id=user_id, payload=fos_payload)
                    entity_id = extract_id_from_response(resp.body) if resp else None
                    if entity_id:
                        persisted_ids.append(str(entity_id))
                elif entity_kind == "asset":
                    fos_payload = asset_payload_to_fos(validated_payload)
                    resp = await persist_asset(user_id=user_id, payload=fos_payload)
                    entity_id = extract_id_from_response(resp.body) if resp else None
                    if entity_id:
                        persisted_ids.append(str(entity_id))
                elif entity_kind == "liability":
                    fos_payload = liability_payload_to_fos(validated_payload)
                    resp = await persist_liability(user_id=user_id, payload=fos_payload)
                    entity_id = extract_id_from_response(resp.body) if resp else None
                    if entity_id:
                        persisted_ids.append(str(entity_id))
                else:
                    logger.warning("[finance_capture] unsupported_entity_kind entity_kind=%s", entity_kind)
            except Exception as exc:  # noqa: BLE001
                error_msg = f"Persistence failed: {exc}"
                logger.error("[finance_capture] persist_failed item=%s error=%s", item_id, exc)
                completion_contexts.append(
                    {
                        "item_id": item_id,
                        "entity_kind": entity_kind,
                        "confirm_decision": "error",
                        "persisted_ids": None,
                        "was_edited": decision == "edit" or item.get("was_edited", False),
                        "draft": draft,
                        "error": error_msg,
                        "completion_message": _build_completion_message(
                            entity_kind=entity_kind,
                            draft=draft,
                            confirm_decision="approve",
                            persisted_ids=None,
                            was_edited=decision == "edit" or item.get("was_edited", False),
                            error=error_msg,
                        ),
                    }
                )
                continue

            completion_contexts.append(
                {
                    "item_id": item_id,
                    "entity_kind": entity_kind,
                    "confirm_decision": decision,
                    "persisted_ids": persisted_ids or None,
                    "was_edited": decision == "edit" or item.get("was_edited", False),
                    "draft": draft,
                    "completion_message": _build_completion_message(
                        entity_kind=entity_kind,
                        draft=draft,
                        confirm_decision=decision,
                        persisted_ids=persisted_ids or None,
                        was_edited=decision == "edit" or item.get("was_edited", False),
                        error=None,
                    ),
                }
            )

        return {
            "completion_contexts": completion_contexts,
            "completion_context": completion_contexts[0] if completion_contexts else None,
            "pending_confirmation_items": None,
            "confirmation_decisions": None,
            "validated": None,
            "capture_draft": None,
            "confirm_decision": None,
            "active_item_id": None,
        }

    def handoff_back(state: FinanceCaptureState) -> dict[str, Any]:
        completion_contexts = state.get("completion_contexts") or []
        if not completion_contexts:
            draft: dict[str, Any] = state.get("validated") or state.get("capture_draft") or {}
            fallback_context = {
                "item_id": draft.get("item_id") or str(uuid.uuid4()),
                "entity_kind": draft.get("entity_kind"),
                "draft": draft,
                "confirm_decision": state.get("confirm_decision") or "approve",
                "persisted_ids": state.get("persisted_ids"),
                "was_edited": state.get("from_edit"),
                "completion_message": _build_completion_message(
                    entity_kind=draft.get("entity_kind"),
                    draft=draft,
                    confirm_decision=state.get("confirm_decision") or "approve",
                    persisted_ids=state.get("persisted_ids"),
                    was_edited=bool(state.get("from_edit")),
                    error=None,
                ),
            }
            completion_contexts = [fallback_context]

        messages = []
        summary_lines = [
            ctx.get("completion_message", "Finance data capture task completed.") for ctx in completion_contexts
        ]
        if len(summary_lines) == 1:
            completion_msg = summary_lines[0]
        else:
            bullet_lines = "\n".join(f"- {line}" for line in summary_lines)
            completion_msg = f"Here’s the status of your items:\n{bullet_lines}"

        original_messages = state.get("messages", [])
        delegator_message = None
        for msg in original_messages:
            role = getattr(msg, "role", None)
            if role is None and isinstance(msg, dict):
                role = msg.get("role")
            name = getattr(msg, "name", None)
            if name is None and isinstance(msg, dict):
                name = msg.get("name")
            if role == "human" and name == "supervisor_delegator":
                delegator_message = msg
                break

        if delegator_message:
            messages.append(delegator_message)

        messages.append(
            {
                "role": "assistant",
                "content": completion_msg,
                "name": "finance_capture_agent",
                "response_metadata": {"is_handoff_back": True},
            }
        )

        aggregate_context = {
            "summary": completion_msg,
            "items": completion_contexts,
        }

        return {
            "messages": messages,
            "from_edit": None,
            "completion_contexts": completion_contexts,
            "completion_context": aggregate_context,
        }

    workflow = StateGraph(FinanceCaptureState)
    workflow.add_node("parse_and_normalize", parse_and_normalize)
    workflow.add_node("fetch_taxonomy_if_needed", fetch_taxonomy_if_needed)
    workflow.add_node("map_categories", map_categories)
    workflow.add_node("validate_schema", validate_schema)
    workflow.add_node("load_next_intent", load_next_intent)
    workflow.add_node("confirm_human", confirm_human)
    workflow.add_node("persist", persist)
    workflow.add_node("handoff_back", handoff_back)

    workflow.add_edge(START, "parse_and_normalize")
    workflow.add_edge("parse_and_normalize", "fetch_taxonomy_if_needed")
    workflow.add_edge("fetch_taxonomy_if_needed", "map_categories")
    workflow.add_edge("map_categories", "validate_schema")
    workflow.add_edge("load_next_intent", "fetch_taxonomy_if_needed")

    def _after_validate(state: FinanceCaptureState) -> str:
        if state.get("from_edit"):
            return "persist"
        queue = state.get("intent_queue") or []
        if queue:
            return "load_next_intent"
        return "confirm_human"

    workflow.add_conditional_edges(
        "validate_schema",
        _after_validate,
        {
            "persist": "persist",
            "confirm_human": "confirm_human",
            "load_next_intent": "load_next_intent",
        },
    )

    def _after_confirm(state: FinanceCaptureState) -> str:
        return "persist"

    workflow.add_conditional_edges("confirm_human", _after_confirm)
    workflow.add_edge("persist", "handoff_back")

    return workflow.compile(checkpointer=checkpointer)
