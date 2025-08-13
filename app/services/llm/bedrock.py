"""Amazon Bedrock LLM provider.

AWS credentials are resolved via the default chain (env vars, profile, role).
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

import boto3

from .base import LLM


class BedrockLLM(LLM):
    def __init__(self) -> None:
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        if not region:
            raise RuntimeError(
                "AWS_REGION (or AWS_DEFAULT_REGION) is required for Bedrock provider"
            )
        self.model_id = os.getenv(
            "BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"
        )
        self.inference_profile_arn = os.getenv("BEDROCK_INFERENCE_PROFILE_ARN")
        self.client = boto3.client("bedrock-runtime", region_name=region)
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.3"))
        self.anthropic_version = "bedrock-2023-05-31"

    def _invoke_claude(
        self,
        messages: list[dict[str, Any]],
        system: Optional[str],
        max_tokens: int = 400,
    ) -> str:
        body: dict[str, Any] = {
            "anthropic_version": self.anthropic_version,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": self.temperature,
        }
        if system:
            body["system"] = system
        kwargs: dict[str, Any] = {
            "body": json.dumps(body).encode("utf-8"),
            "contentType": "application/json",
            "accept": "application/json",
        }
        if self.inference_profile_arn:
            kwargs["inferenceProfileArn"] = self.inference_profile_arn
        else:
            kwargs["modelId"] = self.model_id
        response = self.client.invoke_model(**kwargs)
        payload = json.loads(response["body"].read())
        parts = payload.get("content") or []
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                return str(part.get("text", ""))
        return ""

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> str:
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        return self._invoke_claude(messages, system)

    def extract(
        self,
        schema: dict[str, Any],
        text: str,
        instructions: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        schema_str = json.dumps(schema, ensure_ascii=False)
        instr = instructions or ""
        sys = (
            "You extract structured data from user text. Only output a JSON object that "
            "matches the provided JSON Schema. Do not include any prose."
        )
        usr = (
            f"JSON Schema: {schema_str}\n"
            f"User text: {text}\n"
            f"Instructions: {instr}\n"
            "Rules: Return ONLY JSON. Omit unknown fields. Use null for unknowns."
        )
        messages = [{"role": "user", "content": [{"type": "text", "text": usr}]}]
        raw = self._invoke_claude(messages, sys, max_tokens=500)
        return _safe_parse_json(raw)


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
