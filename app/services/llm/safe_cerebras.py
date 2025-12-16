"""SafeChatCerebras wrapper with guardrail middleware integration."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
from typing import Any, AsyncIterator

from langchain_cerebras import ChatCerebras
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from pydantic import PrivateAttr

from app.services.guardrails import InputGuardrailMiddleware

logger = logging.getLogger(__name__)


class SafeChatCerebras(ChatCerebras):
    """ChatCerebras wrapper with input/output guardrails.

    Validates messages before sending and filters streaming output using
    pattern-based and optional LLM-based classification.

    Example:
        ```python
        safe_chat = SafeChatCerebras(
            model="gpt-oss-120b",
            api_key=config.CEREBRAS_API_KEY,
            input_config={"use_llm_classifier": True},
            output_config={"use_llm_classifier": True, "buffer_size": 50},
            user_context=user_context
        )

        # Stream with validation
        async for chunk in safe_chat.astream(messages):
            print(chunk.content, end="")
        ```

    """

    _input_guardrail: InputGuardrailMiddleware = PrivateAttr()
    _user_context: dict = PrivateAttr(default_factory=dict)

    def __init__(
        self,
        *args,
        input_guardrail: InputGuardrailMiddleware = None,
        input_config: dict | None = None,
        output_config: dict | None = None,
        user_context: dict | None = None,
        fail_open: bool | None = None,
        **kwargs
    ):
        """Initialize SafeChatCerebras.

        Args:
            input_guardrail: Custom input validator (optional)
            input_config: Config for default input validator
            output_config: Config for default output validator
            user_context: User context for validation
            fail_open: If True, allows fail-open behavior in guardrails
            *args: Positional arguments passed to ChatCerebras
            **kwargs: Keyword arguments passed to ChatCerebras
            *args, **kwargs: Passed to ChatCerebras

        """
        super().__init__(*args, **kwargs)

        icfg = (input_config or {}).copy()
        if fail_open is not None:
            icfg.setdefault("fail_open", fail_open)
        ocfg = (output_config or {}).copy()
        if fail_open is not None:
            ocfg.setdefault("fail_open", fail_open)

        self._input_guardrail = input_guardrail or InputGuardrailMiddleware(config=icfg)
        self._user_context = user_context or {}

    @property
    def input_guardrail(self) -> InputGuardrailMiddleware:
        return self._input_guardrail

    @property
    def user_context(self) -> dict:
        return self._user_context

    @user_context.setter
    def user_context(self, value: dict) -> None:
        self._user_context = value or {}

    async def ainvoke(self, messages: list[BaseMessage], config: Any = None, **kwargs) -> Any:
        """Invoke with input validation.

        Args:
            messages: List of messages
            config: Optional LangChain run configuration
            **kwargs: Additional arguments

        Returns:
            AIMessage with response or intervention message

        """
        # Convert to dict format for validation
        msg_dicts = self._messages_to_dicts(messages)

        # Run model call and input validation concurrently to reduce latency
        validate_task = asyncio.create_task(
            self.input_guardrail.validate(msg_dicts, self.user_context)
        )
        model_task = asyncio.create_task(super().ainvoke(messages, config=config, **kwargs))

        done, _ = await asyncio.wait({validate_task, model_task}, return_when=asyncio.FIRST_COMPLETED)

        if validate_task in done:
            is_safe, violation_msg = await validate_task
            if not is_safe:
                with contextlib.suppress(Exception):
                    model_task.cancel()
                logger.warning(f"[SafeCerebras] Input blocked: {violation_msg}")
                content, metadata = self._format_intervention(violation_msg)
                return AIMessage(content=content, response_metadata=metadata)
            # Safe → return model result
            return await model_task
        else:
            # Model finished first; confirm validation before returning
            model_result = await model_task
            is_safe, violation_msg = await validate_task
            if not is_safe:
                logger.warning(f"[SafeCerebras] Input blocked (post-compute): {violation_msg}")
                content, metadata = self._format_intervention(violation_msg)
                return AIMessage(content=content, response_metadata=metadata)
            return model_result

    async def astream(
        self,
        messages: list[BaseMessage],
        config: Any = None,
        **kwargs
    ) -> AsyncIterator[Any]:
        """Stream with input validation.

        Args:
            messages: List of messages
            config: Optional LangChain run configuration
            **kwargs: Additional arguments

        Yields:
            Message chunks or intervention if violated

        """
        # Convert to dict format for validation
        msg_dicts = self._messages_to_dicts(messages)

        # Start validation in background while we set up the model stream
        validate_task = asyncio.create_task(
            self.input_guardrail.validate(msg_dicts, self.user_context)
        )

        # Prepare original stream
        original_stream = super().astream(messages, config=config, **kwargs)

        # Buffer chunks until validation resolves to avoid leaking tokens if unsafe
        buffer: list[Any] = []
        validated_ok = False

        async def _yield_buffered():
            nonlocal buffer
            for buffered_chunk in buffer:
                yield buffered_chunk
            buffer = []

        # Check validation BEFORE starting to iterate stream
        # This handles the case where validation fails so fast that model never emits chunks
        is_safe_initial = None
        violation_msg_initial = None
        if validate_task.done():
            is_safe_initial, violation_msg_initial = await validate_task
            if not is_safe_initial:
                logger.warning(f"[SafeCerebras] Input blocked before stream: {violation_msg_initial}")
                content, metadata = self._format_intervention(violation_msg_initial)
                yield AIMessageChunk(content=content, response_metadata=metadata)
                return

        # Pipe stream after validation check
        async def _validated_stream() -> AsyncIterator[Any]:
            nonlocal validated_ok, buffer
            async for chunk in original_stream:
                if not validate_task.done():
                    buffer.append(chunk)
                    # check if validation finished after buffering this chunk
                    if validate_task.done():
                        is_safe, violation_msg = await validate_task
                        if not is_safe:
                            logger.warning(f"[SafeCerebras] Input blocked in stream: {violation_msg}")
                            content, metadata = self._format_intervention(violation_msg)
                            yield AIMessageChunk(content=content, response_metadata=metadata)
                            return
                        validated_ok = True
                        # flush buffer then continue with current chunk
                        async for flushed in _yield_buffered():
                            yield flushed
                        yield chunk
                    # keep buffering until validation resolves
                    continue
                else:
                    # validation already resolved
                    if not validated_ok:
                        is_safe, violation_msg = await validate_task
                        if not is_safe:
                            logger.warning(f"[SafeCerebras] Input blocked in stream: {violation_msg}")
                            content, metadata = self._format_intervention(violation_msg)
                            yield AIMessageChunk(content=content, response_metadata=metadata)
                            return
                        validated_ok = True
                        # flush any buffered chunks before yielding this one
                        async for flushed in _yield_buffered():
                            yield flushed
                    yield chunk

            # Stream ended; if validation still pending, resolve now
            if not validate_task.done():
                is_safe, violation_msg = await validate_task
                if not is_safe:
                    logger.warning(f"[SafeCerebras] Input blocked in stream (post-end): {violation_msg}")
                    content, metadata = self._format_intervention(violation_msg)
                    yield AIMessageChunk(content=content, response_metadata=metadata)
                    return
                # flush remaining buffer
                async for flushed in _yield_buffered():
                    yield flushed

        # After input validation passes, yield validated chunks
        async for chunk in _validated_stream():
            yield chunk

    def update_user_context(self, user_context: dict):
        """Update user context for guardrail checks.

        Args:
            user_context: New user context

        """
        self.user_context = user_context

    def _messages_to_dicts(self, messages: list[BaseMessage]) -> list[dict]:
        """Convert messages to a single-item dict list for validation.

        Only the latest user message is included, intentionally ignoring
        conversation history and assistant/system messages.
        """
        last_user_content = ""
        for msg in reversed(messages):
            msg_type = getattr(msg, "type", "user")
            if msg_type in ("human", "user"):
                last_user_content = getattr(msg, "content", "")
                break

        return [{"role": "user", "content": last_user_content}]

    def _format_intervention(self, violation_msg: str) -> tuple[str, dict]:
        """Return standardized intervention content and metadata.

        Args:
            violation_msg: Original guardrail message.

        Returns:
            Tuple of (content string, metadata dict).

        """
        base_message = "I'm sorry, but I can't really discuss this topic with you."
        suggestion = self._build_user_context_suggestion()
        human_message = f"{base_message} {suggestion}".strip()
        code = "UNKNOWN"

        # Attempt to extract JSON after marker
        if violation_msg.startswith("[GUARDRAIL_INTERVENED]"):
            json_part_match = re.search(r"\[GUARDRAIL_INTERVENED\]\s*(\{.*\})", violation_msg)
            if json_part_match:
                raw_json = json_part_match.group(1)
                try:
                    data = json.loads(raw_json)
                    code = str(data.get("code", code))
                except Exception:
                    pass
        # Build enriched JSON payload; marker placed at END so supervisor UI keeps human message
        payload = {
            "code": code,
            "message": human_message,
            "suggestion": suggestion,
            "original": violation_msg,
        }
        content = f"{human_message} [GUARDRAIL_INTERVENED] {json.dumps(payload, ensure_ascii=False)}"
        metadata = {
            "guardrail": True,
            "guardrail_code": code,
            "guardrail_message": human_message,
        }
        return content, metadata

    def _build_user_context_suggestion(self) -> str:
        """Generate a redirection hint using available user context."""
        ctx = self.user_context or {}

        def _ctx_get(container: Any, key: str, default: Any = None) -> Any:
            if isinstance(container, dict):
                return container.get(key, default)
            return getattr(container, key, default)

        identity = _ctx_get(ctx, "identity", {}) or {}
        name = _ctx_get(identity, "preferred_name") or _ctx_get(ctx, "preferred_name")

        goals_raw = _ctx_get(ctx, "goals", []) or []
        goals = [str(g) for g in goals_raw if g]

        primary_goal = _ctx_get(ctx, "primary_financial_goal")

        location = _ctx_get(ctx, "location", {}) or {}
        city = _ctx_get(ctx, "city") or _ctx_get(location, "city")

        if goals:
            listed_goals = ", ".join(goals[:2])
            return f"Maybe we can refocus on your goals like {listed_goals}."

        if primary_goal:
            return f"Maybe we can refocus on your goal: {primary_goal}."

        if city:
            return f"Maybe we can talk about your finances in {city}."

        if name:
            return f"Happy to help with your finances, {name}."

        return "Happy to help with your finances or set new goals together."
