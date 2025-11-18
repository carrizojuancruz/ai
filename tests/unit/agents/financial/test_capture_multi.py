from __future__ import annotations

from app.agents.supervisor.finance_capture_agent import nova
from app.agents.supervisor.finance_capture_agent.subgraph import (
    _build_completion_message,
    normalize_confirmation_decisions,
)


def test_normalize_confirmation_decisions_multi_payload() -> None:
    items = [
        {"item_id": "asset-1", "draft": {"entity_kind": "asset"}},
        {"item_id": "asset-2", "draft": {"entity_kind": "asset"}},
    ]
    payload = {
        "decisions": [
            {"item_id": "asset-1", "decision": "approve"},
            {"item_id": "asset-2", "decision": "cancel"},
        ]
    }

    result = normalize_confirmation_decisions(payload, items)

    assert result["asset-1"]["decision"] == "approve"
    assert result["asset-2"]["decision"] == "cancel"


def test_normalize_confirmation_decisions_single_payload_applies_to_all() -> None:
    items = [
        {"item_id": "asset-1", "draft": {"entity_kind": "asset"}},
        {"item_id": "asset-2", "draft": {"entity_kind": "asset"}},
    ]

    result = normalize_confirmation_decisions(True, items)

    assert result["asset-1"]["decision"] == "approve"
    assert result["asset-2"]["decision"] == "approve"


def test_build_completion_message_handles_cancel() -> None:
    message = _build_completion_message(
        entity_kind="asset",
        draft={"name": "Car"},
        confirm_decision="cancel",
        persisted_ids=None,
        was_edited=False,
    )
    assert "car" in message.lower()
    assert "cancelled" in message.lower()


def test_build_completion_message_handles_success() -> None:
    message = _build_completion_message(
        entity_kind="asset",
        draft={"name": "Car", "estimated_value": "45000", "currency_code": "USD"},
        confirm_decision="approve",
        persisted_ids=["123"],
        was_edited=False,
    )
    assert "TASK COMPLETED" in message.upper()


def test_parse_intent_payload_handles_items() -> None:
    payload = {
        "items": [
            {"kind": "asset", "name": "House", "amount": "52000", "currency_code": "USD"},
            {"kind": "asset", "name": "Car", "amount": "22000", "currency_code": "USD"},
        ]
    }
    intents = nova._parse_intent_payload(payload)
    assert len(intents) == 2
    assert intents[0].name == "House"
    assert intents[1].name == "Car"


def test_parse_intent_payload_handles_single_object() -> None:
    payload = {"kind": "asset", "name": "House", "amount": "52000", "currency_code": "USD"}
    intents = nova._parse_intent_payload(payload)
    assert len(intents) == 1
    assert intents[0].name == "House"


def test_clean_json_text_strips_code_fence() -> None:
    text = """```json
{
  "items": [{"kind": "asset", "name": "House"}]
}
```"""
    cleaned = nova._clean_json_text(text)
    assert cleaned.startswith("{")
    assert "items" in cleaned


def test_attempt_json_bracket_extract_handles_array() -> None:
    text = "Here you go: [ {\"kind\": \"asset\"}, {\"kind\": \"asset\"} ] Thanks!"
    payload = nova._attempt_json_bracket_extract(text, "[", "]")
    assert isinstance(payload, list)
    assert len(payload) == 2

