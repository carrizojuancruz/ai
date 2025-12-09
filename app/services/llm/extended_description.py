from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Optional, TypedDict

from app.core.app_state import get_bedrock_runtime_client
from app.core.config import config
from app.services.llm.prompt_loader import prompt_loader

logger = logging.getLogger(__name__)


class ExtendedDescriptionRequest(TypedDict, total=False):
    phase: str
    agent: str
    description: str
    result_text: str | None
    timeline_item_id: str
    source: str | None


_extended_description_provider: Optional[Callable[[ExtendedDescriptionRequest], Awaitable[Optional[str]]]] = None


def set_extended_description_provider(
    provider: Optional[Callable[[ExtendedDescriptionRequest], Awaitable[Optional[str]]]]
) -> None:
    global _extended_description_provider
    _extended_description_provider = provider


def get_extended_description_provider() -> Optional[Callable[[ExtendedDescriptionRequest], Awaitable[Optional[str]]]]:
    return _extended_description_provider


async def _invoke_tiny_llm(prompt: str) -> str:
    model_id = config.MEMORY_TINY_LLM_MODEL_ID
    if not model_id or not prompt:
        return ""

    client = get_bedrock_runtime_client()

    def _do_call() -> str:
        body_payload = {
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"temperature": 0.0, "topP": 0.1, "maxTokens": 120, "stopSequences": []},
        }
        response = client.invoke_model(modelId=model_id, body=json.dumps(body_payload))
        body = response.get("body")
        raw = body.read().decode("utf-8") if hasattr(body, "read") else str(body)
        data = json.loads(raw or "{}")
        text = ""
        try:
            contents = data.get("output", {}).get("message", {}).get("content", "")
            if isinstance(contents, list):
                text = "".join(part.get("text", "") for part in contents if isinstance(part, dict))
            elif isinstance(contents, str):
                text = contents
        except Exception:
            text = data.get("outputText") or data.get("generation") or ""
        return text.strip() if isinstance(text, str) else ""

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, _do_call)
    return result


def sanitize_prompt_value(value: str) -> str:
    if not value:
        return ""
    lines: list[str] = []
    for line in value.splitlines():
        trimmed = line.rstrip()
        if trimmed.strip() == "-":
            continue
        lines.append(trimmed)
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def build_extended_prompt(req: ExtendedDescriptionRequest) -> str:
    agent = req.get("agent") or "agent"
    source = req.get("source") or agent
    base = sanitize_prompt_value(str(req.get("description") or ""))
    result = sanitize_prompt_value(str(req.get("result_text") or ""))
    phase = req.get("phase") or ""
    if phase == "start":
        return prompt_loader.load("timeline_extended_start_prompt", task=base, agent=source)
    return prompt_loader.load("timeline_extended_end_prompt", task=base, agent=source, outcome=result)


def extract_agent_result_text(messages: list[Any]) -> str:
    """Pull the latest non-handoff assistant/ai content as plain text."""

    def _to_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                if isinstance(item, dict):
                    txt = item.get("text") or item.get("content")
                    if isinstance(txt, str):
                        parts.append(txt)
                elif hasattr(item, "content"):
                    part_txt = _to_text(getattr(item, "content", None))
                    if part_txt:
                        parts.append(part_txt)
            return "".join(parts)
        if isinstance(value, dict):
            txt = value.get("content") or value.get("text")
            if isinstance(txt, str):
                return txt
        content_attr = getattr(value, "content", None)
        if isinstance(content_attr, (str, list, dict)):
            return _to_text(content_attr)
        return str(value) if value else ""

    for msg in reversed(messages or []):
        try:
            meta = {}
            if isinstance(msg, dict):
                meta = msg.get("response_metadata", {}) or {}
                name = msg.get("name")
                content = msg.get("content")
                role = msg.get("role")
            else:
                meta = getattr(msg, "response_metadata", {}) or {}
                name = getattr(msg, "name", None)
                content = getattr(msg, "content", None)
                role = getattr(msg, "role", None)

            if meta.get("is_handoff_back"):
                continue

            if role in ("assistant", "ai") or name:
                text = _to_text(content)
                if text and text.strip():
                    return text.strip()
        except Exception:
            continue
    return ""


async def _default_extended_description_provider(req: ExtendedDescriptionRequest) -> Optional[str]:
    prompt = build_extended_prompt(req)
    return await _invoke_tiny_llm(prompt)


def schedule_extended_description_update(
    *,
    queue,
    tool: str,
    source: str,
    description: str,
    timeline_item_id: Optional[str],
    phase: str,
    result_text: Optional[str] = None,
) -> None:
    provider = get_extended_description_provider()
    if not provider or not timeline_item_id:
        return

    async def _runner() -> None:
        try:
            request: ExtendedDescriptionRequest = {
                "phase": phase,
                "agent": tool,
                "source": source,
                "description": description,
                "timeline_item_id": timeline_item_id,
            }
            if result_text is not None:
                request["result_text"] = result_text

            extended = await provider(request)
            if not extended:
                return

            await queue.put(
                {
                    "event": "source.search.update",
                    "data": {
                        "tool": tool,
                        "source": source,
                        "description_extended": extended,
                        "timeline_item_id": timeline_item_id,
                    },
                }
            )
        except Exception:
            logger.info("extended_description_provider failed", exc_info=True)

    asyncio.create_task(_runner())


set_extended_description_provider(_default_extended_description_provider)


