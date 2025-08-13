"""Stub LLM provider for local development.

This provider returns deterministic responses and performs naive extraction.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from .base import LLM


class StubLLM(LLM):
    """A simple provider that does no remote calls."""

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> str:
        return prompt

    def extract(
        self,
        schema: dict[str, Any],
        text: str,
        instructions: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        message = text.strip()
        out: dict[str, Any] = {}

        low = message.lower()
        if "preferred_name" in str(schema).lower():
            name = message.split(" ")[0].strip(",.:;!?")
            if name:
                out["preferred_name"] = name
        if "concise" in low or "direct" in low:
            out["tone"] = "concise"
        elif "warm" in low or "conversational" in low:
            out["tone"] = "warm"
        if any(tok in low for tok in ["avoid", "don't", "not discuss", "no "]):
            blocked = re.sub(
                r".*avoid|.*don't want to discuss|.*not discuss", "", low
            ).strip()
            if blocked:
                out["blocked_categories"] = [
                    b.strip() for b in re.split(r",| and ", blocked) if b.strip()
                ]
        if "feeling" in low or low in {
            "good",
            "bad",
            "stressed",
            "optimistic",
            "curious",
        }:
            out["mood"] = message
        m = re.search(r"in ([A-Za-z]+)", low)
        if m:
            out["city"] = m.group(1).title()
        nums = re.findall(r"\b(\d+)\b", low)
        if nums:
            out["dependents"] = int(nums[0])
        if "goal" in low or low.startswith("pay ") or low.startswith("save "):
            out["primary_financial_goal"] = message
        if "k" in low or "$" in low:
            out["income"] = "provided"
        if low in {"yes", "y", "sure", "ok", "okay"}:
            out["opt_in"] = True
        elif low in {"no", "n", "nope"}:
            out["opt_in"] = False

        return out
