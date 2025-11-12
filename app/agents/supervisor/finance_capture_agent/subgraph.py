from __future__ import annotations

import contextlib
import logging
import uuid
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import interrupt

from app.core.app_state import get_sse_queue
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
    normalize_basic_fields,
    seed_draft_from_intent,
)
from .nova import extract_intent
from .schemas import AssetCreate, LiabilityCreate, ManualTransactionCreate, NovaMicroIntentResult
from .tools import get_taxonomy, persist_asset, persist_liability, persist_manual_transaction


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


def create_finance_capture_graph(
    checkpointer: MemorySaver,
):
    logger = logging.getLogger(__name__)

    async def parse_and_normalize(state: FinanceCaptureState, config: RunnableConfig) -> dict[str, Any]:
        user_message = ""
        for message in reversed(state.get("messages", [])):
            role = getattr(message, "role", getattr(message, "type", None))
            if role in ("user", "human"):
                content = getattr(message, "content", None)
                if isinstance(content, str):
                    user_message = content.strip()
                    break

        intent: NovaMicroIntentResult | None = None
        if user_message:
            intent = extract_intent(user_message)

        update: dict[str, Any] = {}
        if intent is not None:
            update["intent"] = intent.model_dump()
            # Seed working draft fields
            update["capture_draft"] = seed_draft_from_intent(intent)
        return update

    async def fetch_taxonomy_if_needed(state: FinanceCaptureState, config: RunnableConfig) -> dict[str, Any]:
        intent_dict = state.get("intent") or {}
        kind = str(intent_dict.get("kind") or "")
        if kind != "manual_tx":
            return {}

        draft: dict[str, Any] = state.get("capture_draft") or {}
        suggested_category = draft.get("taxonomy_category") or intent_dict.get("suggested_plaid_category")

        scope = "expenses"
        if draft.get("kind") == "income" or isinstance(suggested_category, str) and suggested_category.strip().lower() == "income" or draft.get("vera_income_category"):
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
            categories = taxonomy.get("categories") or []

            suggested_category = draft.get("taxonomy_category") or intent_dict.get("suggested_plaid_category")
            suggested_subcat = draft.get("taxonomy_subcategory") or intent_dict.get("suggested_plaid_subcategory")

            chosen_category, chosen_subcategory, taxonomy_id = choose_from_taxonomy(categories, suggested_category, suggested_subcat)

            if not chosen_category or not chosen_subcategory:
                logger.warning("[finance_capture] taxonomy lookup failed, using Nova's suggestion: category=%r subcategory=%r", suggested_category, suggested_subcat)
                chosen_category = suggested_category or ""
                chosen_subcategory = suggested_subcat or ""
                taxonomy_id = None

            draft["taxonomy_category"] = chosen_category or ""
            draft["taxonomy_subcategory"] = chosen_subcategory or ""
            draft["taxonomy_id"] = taxonomy_id

            # Derive Vera POV category (income vs expense)
            if chosen_category and str(chosen_category).strip().lower() == "income":
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

    async def validate_schema(state: FinanceCaptureState, config: RunnableConfig) -> dict[str, Any]:
        draft: dict[str, Any] = dict(state.get("capture_draft") or {})
        intent_dict = state.get("intent") or {}
        kind = str(intent_dict.get("kind") or draft.get("entity_kind") or "").strip()

        # Normalize basic fields
        normalize_basic_fields(draft)

        was_edit = state.get("confirm_decision") == "edit"

        try:
            if kind == "asset":
                payload = AssetCreate(**asset_payload_from_draft(draft)).model_dump(mode="json")
                payload["entity_kind"] = "asset"
                result = {"validated": payload}
                if was_edit:
                    result["from_edit"] = True
                return result
            if kind == "liability":
                payload = LiabilityCreate(**liability_payload_from_draft(draft)).model_dump(mode="json")
                payload["entity_kind"] = "liability"
                result = {"validated": payload}
                if was_edit:
                    result["from_edit"] = True
                return result
            if kind == "manual_tx":
                payload_dict = manual_tx_payload_from_draft(draft)
                payload = ManualTransactionCreate(**payload_dict).model_dump(mode="json")
                payload["entity_kind"] = draft.get("entity_kind") or draft.get("kind") or "manual_tx"
                result = {"validated": payload}
                if was_edit:
                        result["from_edit"] = True
                return result
        except Exception as exc:  # noqa: BLE001
            logger.warning("[finance_capture] schema_validation_failed kind=%s error=%s", kind, exc)
            # Ask for targeted follow-up: let the model handle the question using system prompt
            return {"messages": [{"role": "assistant", "content": "Could you confirm or provide the missing details?"}]}

        return {}

    async def confirm_human(state: FinanceCaptureState, config: RunnableConfig) -> dict[str, Any]:

        draft: dict[str, Any] = state.get("validated") or state.get("capture_draft") or {}
        summary = build_confirmation_summary(draft)

        confirm_id = get_config_value(config, "confirm_id")

        if not confirm_id:
            confirm_id = str(uuid.uuid4())
            q = get_sse_queue(get_config_value(config, "thread_id"))
            await q.put({
                "event": "confirm.request",
                "data": {
                    "summary": summary,
                    "draft": draft,
                    "confirm_id": confirm_id,
                },
            })

        decision = interrupt({
            "event": "confirm.request",
            "data": {
                "summary": summary,
                "draft": draft,
                "confirm_id": confirm_id,
            },
        })


        decision_str = "approve"
        updated_draft = draft

        if isinstance(decision, dict):
            maybe_draft = decision.get("draft")
            if isinstance(maybe_draft, dict) and maybe_draft:
                updated_draft = {**draft, **maybe_draft}
                decision_str = "edit"  # Route back to validation
            elif "approved" in decision:
                decision_str = "approve" if decision.get("approved") else "cancel"
            else:
                action = str(decision.get("action") or "approve").lower()
                if action in ("approve", "approved", "yes"):
                    decision_str = "approve"
                elif action in ("edit", "update"):
                    decision_str = "edit"
                elif action in ("cancel", "reject", "no"):
                    decision_str = "cancel"
        elif isinstance(decision, bool):
            decision_str = "approve" if decision else "cancel"
        elif isinstance(decision, str):
            action = decision.lower()
            if action in ("approve", "approved", "yes", "true"):
                decision_str = "approve"
            elif action in ("cancel", "reject", "no", "false"):
                decision_str = "cancel"

        update: dict[str, Any] = {"confirm_decision": decision_str, "confirm_id": confirm_id}
        if decision_str == "edit":
            update["capture_draft"] = updated_draft

        return update

    async def persist(state: FinanceCaptureState, config: RunnableConfig) -> dict[str, Any]:
        user_id = get_config_value(config, "user_id")
        draft: dict[str, Any] = state.get("validated") or state.get("capture_draft") or {}

        if not isinstance(user_id, str) or not user_id:
            logger.error("[finance_capture] missing_user_id_for_persist")
            return {"messages": [{"role": "assistant", "content": "Cannot save right now. Missing user id.", "name": "finance_capture_agent"}]}

        persisted_ids: list[str] = []
        entity_kind = draft.get("kind") or draft.get("entity_kind")

        try:
            if entity_kind == "income" or entity_kind == "expense":
                validated_payload = draft  # Already validated by schema
                fos_payload = manual_tx_payload_to_fos(validated_payload)
                resp = await persist_manual_transaction(user_id=user_id, payload=fos_payload)
                entity_id = extract_id_from_response(resp.body) if resp else None
                if entity_id:
                    persisted_ids.append(str(entity_id))
            elif entity_kind == "asset":
                fos_payload = asset_payload_to_fos(draft)
                resp = await persist_asset(user_id=user_id, payload=fos_payload)
                entity_id = extract_id_from_response(resp.body) if resp else None
                if entity_id:
                    persisted_ids.append(str(entity_id))
            elif entity_kind == "liability":
                fos_payload = liability_payload_to_fos(draft)
                resp = await persist_liability(user_id=user_id, payload=fos_payload)
                entity_id = extract_id_from_response(resp.body) if resp else None
                if entity_id:
                    persisted_ids.append(str(entity_id))
        except Exception as exc:  # noqa: BLE001
            logger.error("[finance_capture] persist_failed kind=%s error=%s", entity_kind, exc)
            return {"messages": [{"role": "assistant", "content": "There was an error saving this. Please try again.", "name": "finance_capture_agent"}]}

        state_update: dict[str, Any] = {}
        if persisted_ids:
            state_update["persisted_ids"] = persisted_ids
        state_update["confirm_decision"] = None
        return state_update

    def handoff_back(state: FinanceCaptureState) -> dict[str, Any]:
        draft: dict[str, Any] = state.get("validated") or state.get("capture_draft") or {}
        entity_kind = draft.get("kind") or draft.get("entity_kind")
        confirm_decision = state.get("confirm_decision")
        persisted_ids = state.get("persisted_ids")
        was_edited = state.get("from_edit")

        # Check if task was cancelled
        if confirm_decision and confirm_decision.lower() == "cancel":
            if entity_kind == "asset":
                name = draft.get("name", "asset")
                completion_msg = f"Task cancelled: Asset '{name}' was not saved."
            elif entity_kind == "liability":
                name = draft.get("name", "liability")
                completion_msg = f"Task cancelled: Liability '{name}' was not saved."
            elif entity_kind in ("income", "expense"):
                kind_label = "Income" if entity_kind == "income" else "Expense"
                merchant = draft.get("merchant_or_payee", "transaction")
                completion_msg = f"Task cancelled: {kind_label} transaction for {merchant} was not saved."
            else:
                completion_msg = "Task cancelled: No changes were saved."
        elif persisted_ids:
            if entity_kind == "asset":
                name = draft.get("name", "asset")
                value = draft.get("estimated_value", "")
                currency = draft.get("currency_code", "USD")
                if was_edited:
                    completion_msg = f"TASK COMPLETED: Asset '{name}' worth {value} {currency} has been successfully saved to the user's financial profile. Note: The user edited the original values before saving. No further action needed."
                else:
                    completion_msg = f"TASK COMPLETED: Asset '{name}' worth {value} {currency} has been successfully saved to the user's financial profile. No further action needed."
            elif entity_kind == "liability":
                name = draft.get("name", "liability")
                balance = draft.get("principal_balance", "")
                currency = draft.get("currency_code", "USD")
                if was_edited:
                    completion_msg = f"TASK COMPLETED: Liability '{name}' with balance {balance} {currency} has been successfully saved to the user's financial profile. Note: The user edited the original values before saving. No further action needed."
                else:
                    completion_msg = f"TASK COMPLETED: Liability '{name}' with balance {balance} {currency} has been successfully saved to the user's financial profile. No further action needed."
            elif entity_kind in ("income", "expense"):
                kind_label = "Income" if entity_kind == "income" else "Expense"
                amount = draft.get("amount", "")
                currency = draft.get("currency_code", "USD")
                merchant = draft.get("merchant_or_payee", "transaction")
                if was_edited:
                    completion_msg = f"TASK COMPLETED: {kind_label} transaction for {merchant} ({amount} {currency}) has been successfully saved. Note: The user edited the original values before saving. No further action needed."
                else:
                    completion_msg = f"TASK COMPLETED: {kind_label} transaction for {merchant} ({amount} {currency}) has been successfully saved. No further action needed."
        else:
            # Fallback: no persisted IDs and no cancel decision
            completion_msg = "Finance data capture task completed."

        # Keep only the original delegator message and our completion message
        # Remove all intermediate analysis messages to avoid confusion
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

        # Build clean message list: delegator + completion only
        clean_messages = []
        if delegator_message:
            clean_messages.append(delegator_message)

        clean_messages.append({
            "role": "assistant",
            "content": completion_msg,
            "name": "finance_capture_agent",
            "response_metadata": {"is_handoff_back": True}
        })

        return {"messages": clean_messages, "from_edit": None}

    workflow = StateGraph(FinanceCaptureState)
    workflow.add_node("parse_and_normalize", parse_and_normalize)
    workflow.add_node("fetch_taxonomy_if_needed", fetch_taxonomy_if_needed)
    workflow.add_node("map_categories", map_categories)
    workflow.add_node("validate_schema", validate_schema)
    workflow.add_node("confirm_human", confirm_human)
    workflow.add_node("persist", persist)
    workflow.add_node("handoff_back", handoff_back)

    workflow.add_edge(START, "parse_and_normalize")
    workflow.add_edge("parse_and_normalize", "fetch_taxonomy_if_needed")
    workflow.add_edge("fetch_taxonomy_if_needed", "map_categories")
    workflow.add_edge("map_categories", "validate_schema")

    def _after_validate(state: FinanceCaptureState) -> str:
        if state.get("from_edit"):
            return "persist"
        return "confirm_human"

    workflow.add_conditional_edges("validate_schema", _after_validate, {"persist": "persist", "confirm_human": "confirm_human"})

    def _after_confirm(state: FinanceCaptureState) -> str:
        decision = state.get("confirm_decision")
        if not decision:
            logger.warning("[finance_capture] _after_confirm called with no decision, defaulting to persist")
            return "persist"

        decision = decision.lower()
        if decision == "edit":
            return "validate_schema"
        if decision == "cancel":
            return "handoff_back"
        return "persist"

    workflow.add_conditional_edges("confirm_human", _after_confirm)
    workflow.add_edge("persist", "handoff_back")

    return workflow.compile(checkpointer=checkpointer)


