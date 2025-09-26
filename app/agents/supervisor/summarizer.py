from __future__ import annotations

import logging
from typing import Any, Callable, Sequence

from langchain_core.messages import BaseMessage, HumanMessage, RemoveMessage, SystemMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langmem.short_term import RunningSummary

logger = logging.getLogger(__name__)


class ConversationSummarizer:
    """Summarize the oldest part of a conversation while preserving a recent tail.

    Behavior:
    - Always summarizes when called (no internal thresholding).
    - Keeps the most recent messages up to a token budget (tail_token_budget).
    - Replaces the older messages with a concise SystemMessage summary.
    - Writes a RunningSummary into context for future incremental summarization.
    """

    def __init__(
        self,
        *,
        model: Any,
        token_counter: Callable[[Sequence[BaseMessage]], int],
        tail_token_budget: int = 1500,
        summary_max_tokens: int = 256,
        include_in_summary: Callable[[BaseMessage], bool] | None = None,
        include_in_tail: Callable[[BaseMessage], bool] | None = None,
    ) -> None:
        self.model = model
        self.token_counter = token_counter
        self.tail_token_budget = tail_token_budget
        self.summary_max_tokens = summary_max_tokens
        self.include_in_summary = include_in_summary or self._default_include_predicate
        self.include_in_tail = include_in_tail or self._default_include_predicate

    def as_node(self) -> Callable[[dict[str, Any]], dict[str, Any]]:
        def node(state: dict[str, Any]) -> dict[str, Any]:
            messages = state.get("messages") or []
            context = state.get("context", {}) or {}
            return self.summarize(messages, context)

        return node

    def summarize(self, messages: list[BaseMessage], context: dict[str, Any]) -> dict[str, Any]:
        if not messages:
            return {}

        preserved_tail: list[BaseMessage] = []
        running_total = 0
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            if not self.include_in_tail(msg):
                continue
            t = 0
            try:
                t = self.token_counter([msg])
            except Exception:
                t = 0
            if running_total + t > self.tail_token_budget:
                break
            preserved_tail.append(msg)
            running_total += t
        preserved_tail.reverse()

        preserved_ids = {getattr(m, "id", id(m)) for m in preserved_tail}
        head_messages = [m for m in messages if getattr(m, "id", id(m)) not in preserved_ids]
        head_for_summary = [m for m in head_messages if self.include_in_summary(m)]
        if not head_for_summary:
            if len(preserved_tail) != len(messages):
                return {"messages": [RemoveMessage(REMOVE_ALL_MESSAGES)] + preserved_tail, "context": context}
            return {}

        # Build a focused summarization prompt to avoid answering user queries
        system_instr = (
            "You are a summarizer. Summarize the following earlier conversation strictly as a concise, "
            "factual summary for internal memory. Do not answer user questions. Do not provide step-by-step instructions. "
            f"Limit to roughly {self.summary_max_tokens} tokens. Use 3-7 bullet points, neutral tone."
        )
        transcript = self._messages_to_transcript(head_for_summary)
        prompt_messages = [
            SystemMessage(content=system_instr),
            HumanMessage(content=f"Conversation to summarize:\n{transcript}"),
        ]

        try:
            summary_response = self.model.invoke(prompt_messages)
            summary_text = self._to_plain_text(getattr(summary_response, "content", ""))
        except Exception as exc:
            logger.warning("conversation_summarizer.invoke.failed err=%s", exc)
            return {}

        if not summary_text or not summary_text.strip():
            return {}

        summary_system = SystemMessage(content=f"Summary of the conversation so far:\n{summary_text}")

        try:
            summarized_ids = {m.id for m in head_for_summary if getattr(m, "id", None)}
        except Exception:
            summarized_ids = set()
        last_id = getattr(head_for_summary[-1], "id", None)
        context["running_summary"] = RunningSummary(
            summary=summary_text,
            summarized_message_ids=summarized_ids,
            last_summarized_message_id=last_id,
        )

        new_messages: list[BaseMessage] = [RemoveMessage(REMOVE_ALL_MESSAGES), summary_system] + preserved_tail
        return {"messages": new_messages, "context": context}

    def _messages_to_transcript(self, messages: list[BaseMessage]) -> str:
        lines: list[str] = []
        for msg in messages:
            role = self._format_role(msg)
            text = self._to_plain_text(getattr(msg, "content", None))
            if text:
                lines.append(f"{role}: {text}")
        return "\n".join(lines)

    @staticmethod
    def _format_role(message: BaseMessage) -> str:
        t = getattr(message, "type", "")
        if t in {"human", "user"}:
            return "User"
        if t in {"ai", "assistant"}:
            return "Assistant"
        if t == "system":
            return "System"
        return t or "Message"

    @staticmethod
    def _to_plain_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                if isinstance(item, dict):
                    if item.get("type") == "text" and isinstance(item.get("text"), str):
                        parts.append(item["text"])
                elif hasattr(item, "get"):
                    try:
                        t = item.get("text")
                        if isinstance(t, str):
                            parts.append(t)
                    except Exception:
                        pass
            return "\n".join([p for p in parts if p])
        content = getattr(value, "content", None)
        if isinstance(content, str):
            return content
        return str(value)

    @staticmethod
    def _default_include_predicate(message: BaseMessage) -> bool:
        t = getattr(message, "type", "")
        if t not in {"human", "user", "ai", "assistant"}:
            return False
        meta = getattr(message, "response_metadata", {}) or {}
        try:
            if isinstance(meta, dict) and meta.get("is_handoff_back"):
                return False
        except Exception:
            pass
        content = getattr(message, "content", None)
        if isinstance(content, str):
            stripped = content.strip()
            if stripped.startswith("CONTEXT_PROFILE:") or stripped.startswith("Relevant context for tailoring this turn:"):
                return False
        return True


