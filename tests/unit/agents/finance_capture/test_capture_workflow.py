"""Test graph workflow functions for finance capture agent."""

import pytest

from app.agents.supervisor.finance_capture_agent.subgraph import (
    CaptureConfirmationItem,
    CaptureDecisionPayload,
    _build_completion_message,
    _coerce_single_decision,
    _generate_item_id,
    _serialize_confirmation_items,
    _upsert_confirmation_item,
    _validate_draft_payload,
    normalize_confirmation_decisions,
)


class TestGenerateItemId:
    def test_returns_active_item_id_when_exists(self):
        state = {"active_item_id": "test-id-123"}
        item_id = _generate_item_id(state)
        assert item_id == "test-id-123"

    def test_generates_new_id_when_force_new(self):
        state = {"active_item_id": "test-id-123"}
        item_id = _generate_item_id(state, force_new=True)
        assert item_id != "test-id-123"

    def test_generates_new_id_when_no_active_id(self):
        state = {}
        item_id = _generate_item_id(state)
        assert isinstance(item_id, str)
        assert len(item_id) > 0


class TestUpsertConfirmationItem:
    def test_adds_new_item_to_empty_list(self):
        state = {}
        items = _upsert_confirmation_item(
            state=state,
            item_id="item-1",
            draft={"name": "Test"},
            validated=None,
            entity_kind="asset",
            summary="Test asset",
            was_edited=False,
        )
        assert len(items) == 1
        assert items[0]["item_id"] == "item-1"
        assert items[0]["summary"] == "Test asset"

    def test_updates_existing_item(self):
        state = {
            "pending_confirmation_items": [
                {
                    "item_id": "item-1",
                    "draft": {"name": "Old"},
                    "summary": "Old summary",
                    "validated": None,
                    "entity_kind": "asset",
                    "was_edited": False,
                }
            ]
        }
        items = _upsert_confirmation_item(
            state=state,
            item_id="item-1",
            draft={"name": "New"},
            validated={"name": "Validated"},
            entity_kind="asset",
            summary="New summary",
            was_edited=True,
        )
        assert len(items) == 1
        assert items[0]["draft"]["name"] == "New"
        assert items[0]["validated"]["name"] == "Validated"
        assert items[0]["was_edited"] is True

    def test_adds_second_item(self):
        state = {
            "pending_confirmation_items": [
                {
                    "item_id": "item-1",
                    "draft": {"name": "First"},
                    "summary": "First item",
                    "validated": None,
                    "entity_kind": "asset",
                }
            ]
        }
        items = _upsert_confirmation_item(
            state=state,
            item_id="item-2",
            draft={"name": "Second"},
            validated=None,
            entity_kind="liability",
            summary="Second item",
            was_edited=False,
        )
        assert len(items) == 2
        assert items[0]["item_id"] == "item-1"
        assert items[1]["item_id"] == "item-2"


class TestSerializeConfirmationItems:
    def test_serializes_items_with_validated(self):
        items = [
            {
                "item_id": "item-1",
                "draft": {"name": "Draft"},
                "validated": {"name": "Validated"},
                "summary": "Custom summary",
            }
        ]
        serialized = _serialize_confirmation_items(items)
        assert len(serialized) == 1
        assert serialized[0]["item_id"] == "item-1"
        assert serialized[0]["draft"]["name"] == "Validated"
        assert serialized[0]["summary"] == "Custom summary"

    def test_uses_draft_when_no_validated(self):
        items = [
            {
                "item_id": "item-1",
                "draft": {"name": "Draft"},
                "validated": None,
                "summary": "Test",
            }
        ]
        serialized = _serialize_confirmation_items(items)
        assert serialized[0]["draft"]["name"] == "Draft"

    def test_handles_empty_list(self):
        serialized = _serialize_confirmation_items([])
        assert serialized == []


class TestCoerceSingleDecision:
    def test_approve_decision(self):
        decision, draft = _coerce_single_decision({"action": "approve"})
        assert decision == "approve"
        assert draft is None

    def test_cancel_decision(self):
        decision, draft = _coerce_single_decision({"action": "cancel"})
        assert decision == "cancel"
        assert draft is None

    def test_edit_decision_with_draft(self):
        decision, draft = _coerce_single_decision(
            {"action": "edit", "draft": {"name": "Edited"}}
        )
        assert decision == "edit"
        assert draft == {"name": "Edited"}

    def test_boolean_true(self):
        decision, draft = _coerce_single_decision(True)
        assert decision == "approve"
        assert draft is None

    def test_boolean_false(self):
        decision, draft = _coerce_single_decision(False)
        assert decision == "cancel"
        assert draft is None

    def test_string_approve(self):
        decision, draft = _coerce_single_decision("approve")
        assert decision == "approve"

    def test_string_yes(self):
        decision, draft = _coerce_single_decision("yes")
        assert decision == "approve"

    def test_approved_field(self):
        decision, draft = _coerce_single_decision({"approved": True})
        assert decision == "approve"

    def test_draft_with_cancel_action(self):
        decision, draft = _coerce_single_decision(
            {"draft": {"name": "Test"}, "action": "cancel"}
        )
        assert decision == "cancel"


class TestNormalizeConfirmationDecisions:
    def test_multi_payload_with_decisions_list(self):
        items = [
            {"item_id": "item-1", "draft": {"entity_kind": "asset"}},
            {"item_id": "item-2", "draft": {"entity_kind": "liability"}},
        ]
        payload = {
            "decisions": [
                {"item_id": "item-1", "decision": "approve"},
                {"item_id": "item-2", "decision": "cancel"},
            ]
        }
        result = normalize_confirmation_decisions(payload, items)
        assert result["item-1"]["decision"] == "approve"
        assert result["item-2"]["decision"] == "cancel"

    def test_single_payload_applies_to_all(self):
        items = [
            {"item_id": "item-1", "draft": {}},
            {"item_id": "item-2", "draft": {}},
        ]
        result = normalize_confirmation_decisions(True, items)
        assert result["item-1"]["decision"] == "approve"
        assert result["item-2"]["decision"] == "approve"

    def test_boolean_false_applies_to_all(self):
        items = [
            {"item_id": "item-1", "draft": {}},
            {"item_id": "item-2", "draft": {}},
        ]
        result = normalize_confirmation_decisions(False, items)
        assert result["item-1"]["decision"] == "cancel"
        assert result["item-2"]["decision"] == "cancel"

    def test_dict_without_decisions_applies_to_all(self):
        items = [
            {"item_id": "item-1", "draft": {}},
            {"item_id": "item-2", "draft": {}},
        ]
        result = normalize_confirmation_decisions({"action": "approve"}, items)
        assert result["item-1"]["decision"] == "approve"
        assert result["item-2"]["decision"] == "approve"


class TestValidateDraftPayload:
    def test_validate_asset_draft(self):
        draft = {
            "name": "House",
            "estimated_value": "500000",
            "currency_code": "USD",
            "vera_category": "Real Estate",
        }
        payload, kind = _validate_draft_payload(
            draft=draft,
            intent_dict={"kind": "asset"},
        )
        assert kind == "asset"
        assert payload["name"] == "House"
        assert payload["estimated_value"] in (500000.0, "500000.0")
        assert payload["entity_kind"] == "asset"

    def test_validate_liability_draft(self):
        draft = {
            "name": "Mortgage",
            "principal_balance": "300000",
            "currency_code": "USD",
            "vera_category": "Mortgages",
        }
        payload, kind = _validate_draft_payload(
            draft=draft,
            intent_dict={"kind": "liability"},
        )
        assert kind == "liability"
        assert payload["name"] == "Mortgage"
        assert payload["principal_balance"] in (300000.0, "300000.0")

    def test_validate_manual_tx_draft(self):
        draft = {
            "kind": "income",
            "amount": "5000",
            "currency_code": "USD",
            "taxonomy_category": "Income",
            "taxonomy_subcategory": "Wages",
            "vera_income_category": "Salary & Wages",
        }
        payload, kind = _validate_draft_payload(
            draft=draft,
            intent_dict={"kind": "manual_tx"},
        )
        assert kind in ("manual_tx", "income")
        assert payload["amount"] in (5000.0, "5000")

    def test_unsupported_kind_raises_error(self):
        draft = {"name": "Test"}
        with pytest.raises(ValueError, match="Unsupported entity kind"):
            _validate_draft_payload(draft=draft, intent_dict={"kind": "invalid"})


class TestBuildCompletionMessage:
    def test_asset_success_message(self):
        message = _build_completion_message(
            entity_kind="asset",
            draft={"name": "House", "estimated_value": "500000", "currency_code": "USD"},
            confirm_decision="approve",
            persisted_ids=["123"],
            was_edited=False,
        )
        assert "TASK COMPLETED" in message.upper()
        assert "House" in message
        assert "500000" in message
        assert "USD" in message

    def test_asset_with_edit_note(self):
        message = _build_completion_message(
            entity_kind="asset",
            draft={"name": "Car", "estimated_value": "30000", "currency_code": "USD"},
            confirm_decision="approve",
            persisted_ids=["456"],
            was_edited=True,
        )
        assert "edited" in message.lower()

    def test_liability_success_message(self):
        message = _build_completion_message(
            entity_kind="liability",
            draft={"name": "Mortgage", "principal_balance": "300000", "currency_code": "USD"},
            confirm_decision="approve",
            persisted_ids=["789"],
            was_edited=False,
        )
        assert "TASK COMPLETED" in message.upper()
        assert "Mortgage" in message
        assert "300000" in message

    def test_manual_tx_income_success(self):
        message = _build_completion_message(
            entity_kind="income",
            draft={"amount": "5000", "currency_code": "USD", "merchant_or_payee": "Employer"},
            confirm_decision="approve",
            persisted_ids=["111"],
            was_edited=False,
        )
        assert "TASK COMPLETED" in message.upper()
        assert "Income" in message
        assert "5000" in message

    def test_manual_tx_expense_success(self):
        message = _build_completion_message(
            entity_kind="expense",
            draft={"amount": "150", "currency_code": "USD", "merchant_or_payee": "Restaurant"},
            confirm_decision="approve",
            persisted_ids=["222"],
            was_edited=False,
        )
        assert "TASK COMPLETED" in message.upper()
        assert "Expense" in message
        assert "Restaurant" in message

    def test_cancel_message_asset(self):
        message = _build_completion_message(
            entity_kind="asset",
            draft={"name": "House"},
            confirm_decision="cancel",
            persisted_ids=None,
            was_edited=False,
        )
        assert "cancelled" in message.lower()
        assert "House" in message
        assert "not saved" in message.lower()

    def test_cancel_message_liability(self):
        message = _build_completion_message(
            entity_kind="liability",
            draft={"name": "Loan"},
            confirm_decision="cancel",
            persisted_ids=None,
            was_edited=False,
        )
        assert "cancelled" in message.lower()
        assert "Loan" in message

    def test_cancel_message_transaction(self):
        message = _build_completion_message(
            entity_kind="expense",
            draft={"merchant_or_payee": "Store"},
            confirm_decision="cancel",
            persisted_ids=None,
            was_edited=False,
        )
        assert "cancelled" in message.lower()
        assert "Store" in message

    def test_error_message(self):
        message = _build_completion_message(
            entity_kind="asset",
            draft={"name": "Test"},
            confirm_decision="approve",
            persisted_ids=None,
            was_edited=False,
            error="Validation failed",
        )
        assert "failed" in message.lower()
        assert "Validation failed" in message

    def test_unknown_entity_kind(self):
        message = _build_completion_message(
            entity_kind="unknown",
            draft={},
            confirm_decision="cancel",
            persisted_ids=None,
            was_edited=False,
        )
        assert "cancelled" in message.lower()
