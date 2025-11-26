"""SafeChatCerebras wrapper with guardrail middleware integration."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, AsyncIterator

from langchain_cerebras import ChatCerebras
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from pydantic import PrivateAttr

from app.services.guardrails import InputGuardrailMiddleware, OutputGuardrailMiddleware

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
    _output_guardrail: OutputGuardrailMiddleware = PrivateAttr()
    _user_context: dict = PrivateAttr(default_factory=dict)

    def __init__(
        self,
        *args,
        input_guardrail: InputGuardrailMiddleware = None,
        output_guardrail: OutputGuardrailMiddleware = None,
        input_config: dict | None = None,
        output_config: dict | None = None,
        user_context: dict | None = None,
        fail_open: bool | None = None,
        **kwargs
    ):
        """Initialize SafeChatCerebras.

        Args:
            input_guardrail: Custom input validator (optional)
            output_guardrail: Custom output validator (optional)
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
        self._output_guardrail = output_guardrail or OutputGuardrailMiddleware(config=ocfg)
        self._user_context = user_context or {}

    @property
    def input_guardrail(self) -> InputGuardrailMiddleware:
        return self._input_guardrail

    @property
    def output_guardrail(self) -> OutputGuardrailMiddleware:
        return self._output_guardrail

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

        # Validate input
        is_safe, violation_msg = await self.input_guardrail.validate(
            msg_dicts,
            self.user_context
        )

        if not is_safe:
            logger.warning(f"[SafeCerebras] Input blocked: {violation_msg}")
            content, metadata = self._format_intervention(violation_msg)
            return AIMessage(content=content, response_metadata=metadata)

        # Call original if safe
        return await super().ainvoke(messages, config=config, **kwargs)

    async def astream(
        self,
        messages: list[BaseMessage],
        config: Any = None,
        **kwargs
    ) -> AsyncIterator[Any]:
        """Stream with input validation and output filtering.

        Args:
            messages: List of messages
            config: Optional LangChain run configuration
            **kwargs: Additional arguments

        Yields:
            Message chunks or intervention if violated

        """
        # Convert to dict format for validation
        msg_dicts = self._messages_to_dicts(messages)

        # Validate input
        is_safe, violation_msg = await self.input_guardrail.validate(
            msg_dicts,
            self.user_context
        )

        if not is_safe:
            logger.warning(f"[SafeCerebras] Input blocked in stream: {violation_msg}")
            content, metadata = self._format_intervention(violation_msg)
            yield AIMessageChunk(content=content, response_metadata=metadata)
            return

        # Stream with output validation
        original_stream = super().astream(messages, config=config, **kwargs)

        async for chunk in self.output_guardrail.validate_stream(
            original_stream,
            self.user_context
        ):
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
        default_human = (
            "I’m sorry, but I can’t really discuss this topic with you. Let’s change the subject, maybe?"
        )
        code = "UNKNOWN"
        human_message = default_human

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
        payload = {"code": code, "message": human_message, "original": violation_msg}
        content = f"{human_message} [GUARDRAIL_INTERVENED] {json.dumps(payload, ensure_ascii=False)}"
        metadata = {
            "guardrail": True,
            "guardrail_code": code,
            "guardrail_message": human_message,
        }
        return content, metadata
