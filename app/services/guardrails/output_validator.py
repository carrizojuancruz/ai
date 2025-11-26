"""Output validation middleware for streaming responses."""

from __future__ import annotations

import logging
import re
from typing import Any, AsyncIterator

from app.services.guardrails.llm_safety_classifier import LLMSafetyMiddleware

logger = logging.getLogger(__name__)


class OutputGuardrailMiddleware:
    """Validates streaming output from LLM in real-time.

    Combines pattern-based checks with optional LLM-based classification.
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.buffer_size = self.config.get("buffer_size", 50)
        self.enabled_checks = self.config.get("enabled_checks", [
            "pii_leakage", "context_exposure"
        ])
        self.use_llm_classifier = self.config.get("use_llm_classifier", False)

        # Initialize LLM classifier if enabled
        if self.use_llm_classifier:
            self.llm_middleware = LLMSafetyMiddleware(
                confidence_threshold=self.config.get("llm_confidence_threshold", 0.7),
                fail_open=self.config.get("llm_fail_open", True)
            )
        else:
            self.llm_middleware = None

    async def validate_stream(
        self,
        stream: AsyncIterator[Any],
        user_context: dict = None
    ) -> AsyncIterator[Any]:
        """Validate streaming output in real-time."""
        buffer = []
        total_content = ""
        violation_detected = False

        try:
            async for chunk in stream:
                chunk_content = self._extract_content(chunk)

                if chunk_content:
                    buffer.append(chunk_content)
                    total_content += chunk_content

                    # Check buffer when threshold reached
                    if len(buffer) >= self.buffer_size:
                        buffer_text = "".join(buffer[-self.buffer_size:])

                        # Pattern-based checks
                        is_safe, violation_msg = await self._validate_buffer_patterns(
                            buffer_text,
                            user_context
                        )

                        if not is_safe:
                            violation_detected = True
                            logger.warning(f"[OutputGuardrail] Pattern violation: {violation_msg}")
                            yield self._create_intervention_chunk(violation_msg)
                            break

                        # LLM-based check if enabled
                        if self.use_llm_classifier and self.llm_middleware:
                            is_safe, violation_msg = await self.llm_middleware.validate_output(
                                buffer_text,
                                user_context
                            )

                            if not is_safe:
                                violation_detected = True
                                logger.warning(f"[OutputGuardrail] LLM violation: {violation_msg}")
                                yield self._create_intervention_chunk(violation_msg)
                                break

                # Yield original chunk if safe
                if not violation_detected:
                    yield chunk

            # Final validation on complete response
            if not violation_detected and total_content:
                is_safe, violation_msg = await self._validate_complete(
                    total_content,
                    user_context
                )

                if not is_safe:
                    logger.warning(f"[OutputGuardrail] Final check failed: {violation_msg}")
                    # Too late to stop stream, but log for monitoring

        except Exception as e:
            logger.error(f"[OutputGuardrail] Stream validation error: {e}")
            # Fail open: continue streaming

    def _extract_content(self, chunk: Any) -> str:
        """Extract text content from chunk."""
        if isinstance(chunk, str):
            return chunk

        if hasattr(chunk, "content"):
            content = chunk.content
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                return "".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in content
                )

        if isinstance(chunk, dict):
            return chunk.get("content", "")

        return ""

    async def _validate_buffer_patterns(
        self,
        text: str,
        user_context: dict = None
    ) -> tuple[bool, str | None]:
        """Validate buffer using pattern-based checks."""
        if "pii_leakage" in self.enabled_checks and not await self._check_no_pii_leak(text):
            return False, "PII_LEAKAGE"

        if "context_exposure" in self.enabled_checks and not await self._check_no_context_exposure(text):
            return False, "CONTEXT_EXPOSURE"

        return True, None

    async def _validate_complete(
        self,
        text: str,
        user_context: dict = None
    ) -> tuple[bool, str | None]:
        """Last validation on complete response."""
        # Pattern checks
        is_safe, violation_msg = await self._validate_buffer_patterns(text, user_context)
        if not is_safe:
            return False, violation_msg

        # LLM check on full response if enabled
        if self.use_llm_classifier and self.llm_middleware:
            return await self.llm_middleware.validate_output(text, user_context)

        return True, None

    async def _check_no_pii_leak(self, text: str) -> bool:
        """Ensure we're not leaking PII."""
        pii_patterns = [
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
            r'\b\d{16}\b',  # Credit card
            r'\b\d{3}-\d{3}-\d{4}\b',  # Phone
        ]

        for pattern in pii_patterns:
            if re.search(pattern, text):
                logger.warning("[OutputGuardrail] PII leak detected")
                return False
        return True

    async def _check_no_context_exposure(self, text: str) -> bool:
        """Ensure we're not exposing internal context."""
        exposure_patterns = [
            r'CONTEXT_PROFILE:',
            r'Relevant context for tailoring',
            r'\[(Finance|Goals|Personal)\]',
            r'user_id.*[0-9a-f]{8}-[0-9a-f]{4}',
        ]

        for pattern in exposure_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning(f"[OutputGuardrail] Context exposure: {pattern}")
                return False
        return True

    def _create_intervention_chunk(self, violation_type: str) -> Any:
        """Create intervention chunk."""
        return {
            "content": f"[GUARDRAIL_INTERVENED] {{\"code\":\"{violation_type}\"}}",
            "type": "guardrail_intervention"
        }
