from __future__ import annotations

import json
import logging

from app.core.app_state import get_bedrock_runtime_client
from app.core.config import config
from app.services.llm.prompt_loader import prompt_loader

from .constants import AssetCategory, LiabilityCategory, VeraPovExpenseCategory
from .schemas import NovaMicroIntentResult

logger = logging.getLogger(__name__)


def _format_plaid_expense_categories() -> tuple[str, ...]:
    return tuple(category.value for category in VeraPovExpenseCategory)


def _format_asset_categories() -> tuple[str, ...]:
    return tuple(category.value for category in AssetCategory)


def _format_liability_categories() -> tuple[str, ...]:
    return tuple(category.value for category in LiabilityCategory)


def _load_prompt(user_message: str) -> str:
    return prompt_loader.load(
        "finance_capture_nova_intent_prompt",
        text=user_message,
        allowed_kinds=("asset", "liability", "manual_tx"),
        plaid_expense_categories=_format_plaid_expense_categories(),
        asset_categories=_format_asset_categories(),
        liability_categories=_format_liability_categories(),
    )


def _extract_text_from_response(data: dict[str, object]) -> str:
    output = data.get("output")
    if isinstance(output, dict):
        message = output.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, list):
                texts: list[str] = []
                for part in content:
                    if isinstance(part, dict):
                        text = part.get("text")
                        if isinstance(text, str):
                            texts.append(text)
                if texts:
                    return "".join(texts).strip()
    output_text = data.get("outputText")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()
    generation = data.get("generation")
    if isinstance(generation, str) and generation.strip():
        return generation.strip()
    return ""


def _invoke_nova(prompt: str) -> dict[str, object]:
    model_id = config.MEMORY_TINY_LLM_MODEL_ID
    if not model_id:
        raise RuntimeError("MEMORY_TINY_LLM_MODEL_ID is not configured")

    body_payload = {
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"temperature": 0.0, "topP": 0.1, "maxTokens": 180, "stopSequences": []},
    }

    client = get_bedrock_runtime_client()
    response = client.invoke_model(modelId=model_id, body=json.dumps(body_payload))
    body = response.get("body")
    raw = body.read().decode("utf-8") if hasattr(body, "read") else str(body)
    return json.loads(raw or "{}")


def extract_intent(user_message: str) -> NovaMicroIntentResult | None:
    prompt = _load_prompt(user_message)
    try:
        response_data = _invoke_nova(prompt)
    except Exception as exc:  # noqa: BLE001
        logger.error("finance_capture.nova.invoke_failed: %s", exc)
        return None

    text = _extract_text_from_response(response_data)
    if not text:
        logger.warning("finance_capture.nova.empty_output")
        return None

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Attempt to salvage JSON substring
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            logger.warning("finance_capture.nova.invalid_json: %s", text)
            return None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            logger.warning("finance_capture.nova.json_extract_failed: %s", text)
            return None

    try:
        kind = str(parsed.get("kind")) if isinstance(parsed, dict) else ""
        if kind in ("asset", "liability") and isinstance(parsed, dict):
            parsed.pop("date", None)
        return NovaMicroIntentResult.model_validate(parsed)
    except Exception as exc:  # noqa: BLE001
        logger.warning("finance_capture.nova.schema_validation_failed: %s payload=%s", exc, parsed)
        return None


