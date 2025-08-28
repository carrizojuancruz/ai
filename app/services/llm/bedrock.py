from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import config

from .base import LLM


class BedrockLLM(LLM):
    def __init__(self) -> None:
        region = config.get_aws_region()
        if not region:
            raise RuntimeError("AWS_REGION (or AWS_DEFAULT_REGION) is required for Bedrock provider")
        self.model_id = config.BEDROCK_MODEL_ID
        self.temperature = config.LLM_TEMPERATURE
        self.chat_model = ChatBedrock(
            model_id=self.model_id,
            region_name=region,
            model_kwargs={
                "temperature": self.temperature,
                "max_tokens": 400,
            },
        )
        self._callbacks: list[Any] | None = None

    def set_callbacks(self, callbacks: list[Any] | None) -> None:
        self._callbacks = callbacks
        if self.chat_model and callbacks:
            self.chat_model.callbacks = callbacks

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        response = self.chat_model.invoke(messages, config={"callbacks": self._callbacks} if self._callbacks else None)
        return response.content

    async def generate_stream(
        self,
        prompt: str,
        system: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        async for chunk in self.chat_model.astream(
            messages, config={"callbacks": self._callbacks} if self._callbacks else None
        ):
            if hasattr(chunk, "content") and chunk.content:
                yield chunk.content

    def extract(
        self,
        schema: dict[str, Any],
        text: str,
        instructions: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        schema_str = json.dumps(schema, ensure_ascii=False)
        instr = instructions or ""
        system = (
            "You extract structured data from user text. Only output a JSON object that "
            "matches the provided JSON Schema. Do not include any prose."
        )
        prompt = (
            f"JSON Schema: {schema_str}\n"
            f"User text: {text}\n"
            f"Instructions: {instr}\n"
            "Rules: Return ONLY JSON. Omit unknown fields. Use null for unknowns."
        )
        response = self.generate(prompt, system)
        return _safe_parse_json(response)


def _safe_parse_json(raw: str) -> dict[str, Any]:
    try:
        return json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except Exception:
                return {}
        return {}
