"""Input validation middleware with pattern-based and LLM-based checks."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


class InputGuardrailMiddleware:
    """Validates input before sending to LLM.

    Combines pattern-based checks (fast) with optional LLM-based classification (accurate).
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.enabled_checks = self.config.get("enabled_checks", [
            "pii", "injection", "blocked_topics"
        ])
        self.use_llm_classifier = self.config.get("use_llm_classifier", False)

        # Initialize LLM classifier if enabled
        if self.use_llm_classifier:
            from app.services.guardrails.llm_safety_classifier import LLMSafetyMiddleware
            self.llm_middleware = LLMSafetyMiddleware(
                confidence_threshold=self.config.get("llm_confidence_threshold", 0.7),
                fail_open=self.config.get("llm_fail_open", True)
            )
        else:
            self.llm_middleware = None

    async def validate(
        self,
        messages: list[dict],
        user_context: dict = None
    ) -> tuple[bool, str | None]:
        """Validate input messages against guardrails.

        Args:
            messages: List of message dicts with role/content
            user_context: Optional user context

        Returns:
            (is_safe, violation_message)

        """
        try:
            # 1. Fast pattern-based checks first
            if "pii" in self.enabled_checks and not await self._check_pii(messages):
                return False, "[GUARDRAIL_INTERVENED] {\"code\":\"PII_DETECTED\"}"

            if "injection" in self.enabled_checks and not await self._check_injection(messages):
                return False, "[GUARDRAIL_INTERVENED] {\"code\":\"PROMPT_INJECTION\"}"

            if "blocked_topics" in self.enabled_checks and user_context and not await self._check_blocked_topics(messages, user_context):
                return False, "[GUARDRAIL_INTERVENED] {\"code\":\"BLOCKED_TOPIC\"}"

            # 2. LLM-based classification if enabled (more comprehensive)
            if self.use_llm_classifier and self.llm_middleware:
                is_safe, violation_msg = await self.llm_middleware.validate_input(
                    messages,
                    user_context
                )
                if not is_safe:
                    return False, violation_msg

            return True, None

        except Exception as e:
            logger.error(f"[InputGuardrail] Validation error: {e}")
            # Fail open by default
            return True, None

    async def _check_pii(self, messages: list[dict]) -> bool:
        """Detect PII exposure attempts."""
        pii_patterns = [
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
            r'\b\d{16}\b',  # Credit card (basic)
            r'\b\d{3}-\d{3}-\d{4}\b',  # Phone number
        ]

        for msg in messages:
            content = str(msg.get("content", ""))
            for pattern in pii_patterns:
                if re.search(pattern, content):
                    logger.warning("[InputGuardrail] PII pattern detected")
                    return False
        return True

    async def _check_injection(self, messages: list[dict]) -> bool:
        """Detect prompt injection attempts."""
        injection_patterns = [
            r'ignore\s+(previous|all|your)\s+instructions',
            r'disregard\s+.*\s+(above|before|previous)',
            r'you\s+are\s+now',
            r'new\s+instructions',
            r'CONTEXT_PROFILE:',
            r'ICEBREAKER_CONTEXT:',
            r'system.*role',
        ]

        for msg in messages:
            content = str(msg.get("content", ""))
            for pattern in injection_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    logger.warning(f"[InputGuardrail] Injection pattern detected: {pattern}")
                    return False
        return True

    async def _check_blocked_topics(
        self,
        messages: list[dict],
        user_context: dict
    ) -> bool:
        """Check against user's blocked topics."""
        blocked_topics = user_context.get("blocked_topics", [])
        if not blocked_topics:
            return True

        for msg in messages:
            content = str(msg.get("content", "")).lower()
            for topic in blocked_topics:
                if topic.lower() in content:
                    logger.info(f"[InputGuardrail] Blocked topic detected: {topic}")
                    return False
        return True
