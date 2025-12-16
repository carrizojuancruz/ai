from __future__ import annotations

import logging
import math
from typing import Any, Callable

from langchain_core.messages import BaseMessage, HumanMessage, RemoveMessage, SystemMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langmem.short_term import RunningSummary

logger = logging.getLogger(__name__)

DEFAULT_CHARS_PER_TOKEN: int = 4
MIN_ESTIMATED_TOKENS: int = 1


class ConversationSummarizer:
    """Summarize the oldest part of a conversation while preserving a recent tail.

    Behavior:
    - Always summarizes when called (no internal thresholding).
    - Keeps a recent tail of dialogue turns selected by token budget (tail_token_budget).
    - Replaces the older messages with a concise SystemMessage summary.
    - Writes a RunningSummary into context for future incremental summarization.
    """

    def __init__(
        self,
        *,
        model: Any,
        tail_token_budget: int = 3500,
        summary_max_tokens: int = 256,
        include_in_summary: Callable[[BaseMessage], bool] | None = None,
        include_in_tail: Callable[[BaseMessage], bool] | None = None,
    ) -> None:
        self.model = model
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

        dialogue_messages = [m for m in messages if self.include_in_tail(m)]
        dialogue_turns = self._split_dialogue_turns(dialogue_messages)
        preserved_turns = self._select_tail_turns_by_token_budget(dialogue_turns, self.tail_token_budget)
        if len(preserved_turns) >= len(dialogue_turns):
            return {}

        head_turns = dialogue_turns[: len(dialogue_turns) - len(preserved_turns)]
        preserved_tail = self._flatten_dialogue_turns(preserved_turns)
        head_for_summary = self._flatten_dialogue_turns(head_turns)
        if not head_for_summary:
            return {}

        # Build a focused summarization prompt to avoid answering user queries
        from app.services.llm.prompt_loader import prompt_loader
        system_instr = prompt_loader.load(
            "conversation_summarizer_instruction",
            summary_max_tokens=self.summary_max_tokens,
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
            raise exc

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
        logger.info(
            "summary.completed head_turns=%s head_messages=%s preserved_turns=%s preserved_tail_messages=%s",
            len(head_turns),
            len(head_for_summary),
            len(preserved_turns),
            len(preserved_tail),
        )
        return {"messages": new_messages, "context": context}

    @staticmethod
    def _estimate_tokens_for_text(text: str, *, chars_per_token: int = DEFAULT_CHARS_PER_TOKEN) -> int:
        if not text:
            return MIN_ESTIMATED_TOKENS
        return max(MIN_ESTIMATED_TOKENS, int(math.ceil(len(text) / chars_per_token)))

    def _estimate_tokens_for_message(self, message: BaseMessage) -> int:
        raw_text = self._to_plain_text(getattr(message, "content", None))
        return self._estimate_tokens_for_text(raw_text.strip())

    def _estimate_tokens_for_turn(self, turn: tuple[BaseMessage, list[BaseMessage]]) -> int:
        human, assistants = turn
        total = self._estimate_tokens_for_message(human)
        for msg in assistants:
            total += self._estimate_tokens_for_message(msg)
        return total

    def _select_tail_turns_by_token_budget(
        self,
        dialogue_turns: list[tuple[BaseMessage, list[BaseMessage]]],
        token_budget: int,
    ) -> list[tuple[BaseMessage, list[BaseMessage]]]:
        if not dialogue_turns:
            return []
        if token_budget <= 0:
            return [dialogue_turns[-1]]

        selected: list[tuple[BaseMessage, list[BaseMessage]]] = []
        total_tokens = 0

        for turn in reversed(dialogue_turns):
            turn_tokens = self._estimate_tokens_for_turn(turn)
            if selected and (total_tokens + turn_tokens > token_budget):
                break
            selected.append(turn)
            total_tokens += turn_tokens

        selected.reverse()
        return selected

    @staticmethod
    def _split_dialogue_turns(
        messages: list[BaseMessage],
    ) -> list[tuple[BaseMessage, list[BaseMessage]]]:
        turns: list[tuple[BaseMessage, list[BaseMessage]]] = []
        current_human: BaseMessage | None = None
        current_ai: list[BaseMessage] = []

        for msg in messages:
            msg_type = getattr(msg, "type", "")
            if msg_type in {"human", "user"}:
                if current_human is not None:
                    turns.append((current_human, current_ai))
                current_human = msg
                current_ai = []
                continue

            if msg_type in {"ai", "assistant"}:
                if current_human is None:
                    continue
                current_ai.append(msg)

        if current_human is not None:
            turns.append((current_human, current_ai))

        return turns

    @staticmethod
    def _flatten_dialogue_turns(turns: list[tuple[BaseMessage, list[BaseMessage]]]) -> list[BaseMessage]:
        flattened: list[BaseMessage] = []
        for human, assistants in turns:
            flattened.append(human)
            flattened.extend(assistants)
        return flattened

    def _messages_to_transcript(self, messages: list[BaseMessage]) -> str:
        lines: list[str] = []
        last_role: str | None = None
        last_text: str | None = None
        for msg in messages:
            role = self._format_role(msg)
            raw_text = self._to_plain_text(getattr(msg, "content", None))
            text = raw_text.strip()
            if not text:
                continue
            if last_role == role and last_text == text:
                continue
            last_role = role
            last_text = text
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
                    except (AttributeError, TypeError, KeyError):
                        continue
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
        name = getattr(message, "name", None)
        if name and name != "supervisor":
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
            if stripped.startswith("====="):
                return False
        return True


