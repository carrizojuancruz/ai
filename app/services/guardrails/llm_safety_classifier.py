"""LLM-based safety classifier for content validation.

Uses a small, fast LLM to classify content safety in real-time.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from langchain_cerebras import ChatCerebras
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import config
from app.services.llm.prompt_loader import prompt_loader

logger = logging.getLogger(__name__)


class SafetyLevel(Enum):
    """Safety classification levels."""

    SAFE = "safe"
    UNSAFE = "unsafe"
    UNCERTAIN = "uncertain"


class SafetyCategory(Enum):
    """Categories of unsafe content."""

    HATE_SPEECH = "hate_speech"
    VIOLENCE = "violence"
    SEXUAL = "sexual"
    SELF_HARM = "self_harm"
    HARASSMENT = "harassment"
    ILLEGAL = "illegal"
    PII_EXPOSURE = "pii_exposure"
    PROMPT_INJECTION = "prompt_injection"
    MISINFORMATION = "misinformation"
    INTERNAL_EXPOSURE = "internal_exposure"


class SafetyClassification:
    """Result of safety classification."""

    def __init__(
        self,
        level: SafetyLevel,
        categories: list[SafetyCategory] = None,
        confidence: float = 0.0,
        reasoning: str = ""
    ):
        self.level = level
        self.categories = categories or []
        self.confidence = confidence
        self.reasoning = reasoning

    @property
    def is_safe(self) -> bool:
        """Check if content is safe."""
        return self.level == SafetyLevel.SAFE

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "level": self.level.value,
            "categories": [cat.value for cat in self.categories],
            "confidence": self.confidence,
            "reasoning": self.reasoning
        }


class LLMSafetyClassifier:
    """LLM-based safety classifier using fast inference.

    with structured output for reliable parsing.
    """

    def __init__(self, model: str = "gpt-oss-120b", temperature: float = 0.0):
        """Initialize LLM safety classifier.

        Args:
            model: Model to use for classification (default: gpt-oss-120b for speed)
            temperature: Temperature for LLM (default: 0.0 for consistency)

        """
        self.model = model
        self.temperature = temperature
        self._llm = None
        self._safety_prompt = None

    @property
    def SAFETY_SYSTEM_PROMPT(self) -> str:
        """Get safety system prompt from prompt loader."""
        if self._safety_prompt is None:
            self._safety_prompt = prompt_loader.load("safety_system_prompt")
        return self._safety_prompt

    def _get_llm(self) -> ChatCerebras:
        """Lazy initialization of LLM."""
        if self._llm is None:
            self._llm = ChatCerebras(
                model=self.model,
                api_key=config.CEREBRAS_API_KEY,
                temperature=self.temperature,
            )
        return self._llm

    async def classify(self, text: str, context: str = "") -> SafetyClassification:
        """Classify text for safety.

        Args:
            text: Text to classify
            context: Optional context for better classification

        Returns:
            SafetyClassification result

        """
        try:
            llm = self._get_llm()

            # Build prompt with context if provided
            user_prompt = self._build_user_prompt(text, context)

            messages = [
                SystemMessage(content=self.SAFETY_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt)
            ]

            # Get classification
            response = await llm.ainvoke(messages)

            # Parse response
            classification = self._parse_response(response.content)

            logger.info(
                f"[LLMSafetyClassifier] Classification: {classification.level.value} "
                f"(confidence: {classification.confidence:.2f})"
            )

            return classification

        except Exception as e:
            logger.error(f"[LLMSafetyClassifier] Classification failed: {e}")
            # Fail-safe: return uncertain
            return SafetyClassification(
                level=SafetyLevel.UNCERTAIN,
                confidence=0.0,
                reasoning=f"Classification error: {str(e)}"
            )

    async def classify_batch(
        self,
        texts: list[str],
        context: str = ""
    ) -> list[SafetyClassification]:
        """Classify multiple texts.

        Args:
            texts: List of texts to classify
            context: Optional shared context

        Returns:
            List of SafetyClassification results

        """
        import asyncio

        tasks = [self.classify(text, context) for text in texts]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        classifications = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"[LLMSafetyClassifier] Batch item {i} failed: {result}")
                classifications.append(SafetyClassification(
                    level=SafetyLevel.UNCERTAIN,
                    confidence=0.0,
                    reasoning=f"Error: {str(result)}"
                ))
            else:
                classifications.append(result)

        return classifications

    def _build_user_prompt(self, text: str, context: str = "") -> str:
        """Build user prompt with optional context."""
        if context:
            return f"""Context: {context}

Content to classify:
{text}"""
        else:
            return f"""Content to classify:
{text}"""

    def _parse_response(self, response: str) -> SafetyClassification:
        """Parse LLM response into SafetyClassification."""
        import json
        import re

        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
            data = json.loads(json_match.group()) if json_match else self._parse_text_response(response)

            # Extract level
            level_str = data.get("level", "UNCERTAIN").upper()
            level = SafetyLevel.SAFE if level_str == "SAFE" else SafetyLevel.UNSAFE

            # Extract categories
            categories = []
            for cat_str in data.get("categories", []):
                try:
                    categories.append(SafetyCategory(cat_str.lower()))
                except ValueError:
                    logger.warning(f"[LLMSafetyClassifier] Unknown category: {cat_str}")

            # Extract confidence and reasoning
            confidence = float(data.get("confidence", 0.5))
            reasoning = data.get("reasoning", "")

            return SafetyClassification(
                level=level,
                categories=categories,
                confidence=confidence,
                reasoning=reasoning
            )

        except Exception as e:
            logger.warning(f"[LLMSafetyClassifier] Parse error: {e}, response: {response}")
            # Fallback: simple keyword detection
            return self._fallback_classification(response)

    def _parse_text_response(self, text: str) -> dict[str, Any]:
        """Fallback parser for non-JSON responses."""
        data = {}

        # Extract level
        if "SAFE" in text.upper() and "UNSAFE" not in text.upper():
            data["level"] = "SAFE"
        elif "UNSAFE" in text.upper():
            data["level"] = "UNSAFE"
        else:
            data["level"] = "UNCERTAIN"

        # Extract categories (simple keyword search)
        categories = []
        for category in SafetyCategory:
            if category.value.replace("_", " ") in text.lower():
                categories.append(category.value)
        data["categories"] = categories

        # Default confidence
        data["confidence"] = 0.5
        data["reasoning"] = text[:200]  # First 200 chars as reasoning

        return data

    def _fallback_classification(self, response: str) -> SafetyClassification:
        """Ultra-simple fallback when parsing fails."""
        response_lower = response.lower()

        # Check for clear unsafe indicators
        unsafe_keywords = ["unsafe", "violation", "harmful", "inappropriate"]
        is_unsafe = any(keyword in response_lower for keyword in unsafe_keywords)

        if is_unsafe:
            return SafetyClassification(
                level=SafetyLevel.UNSAFE,
                confidence=0.3,
                reasoning="Fallback detection based on keywords"
            )
        else:
            return SafetyClassification(
                level=SafetyLevel.SAFE,
                confidence=0.3,
                reasoning="Fallback detection - appears safe"
            )


class LLMSafetyMiddleware:
    """Middleware that uses LLM-based safety classification.

    This can be used as input/output validator with LLM intelligence.
    """

    def __init__(
        self,
        classifier: LLMSafetyClassifier = None,
        confidence_threshold: float = 0.7,
        fail_open: bool = True
    ):
        """Initialize middleware.

        Args:
            classifier: LLM safety classifier instance
            confidence_threshold: Minimum confidence to trust classification (0-1)
            fail_open: If True, allow content on errors/uncertainty

        """
        self.classifier = classifier or LLMSafetyClassifier()
        self.confidence_threshold = confidence_threshold
        self.fail_open = fail_open

    async def validate_input(
        self,
        messages: list[dict],
        user_context: dict = None
    ) -> tuple[bool, str | None]:
        """Validate input messages before sending to LLM.

        Args:
            messages: List of message dicts with role/content
            user_context: Optional user context for classification

        Returns:
            (is_safe, violation_message)

        """
        # Combine messages into single text for classification
        combined_text = "\n\n".join([
            f"{msg.get('role', 'user')}: {msg.get('content', '')}"
            for msg in messages
            if msg.get('content')
        ])

        if not combined_text.strip():
            return True, None

        # Build context
        context = self._build_context(user_context, "input")

        # Classify
        classification = await self.classifier.classify(combined_text, context)
        logger.info(
            "[LLMSafetyMiddleware][input] level=%s confidence=%.2f categories=%s",
            classification.level.value,
            classification.confidence,
            [cat.value for cat in classification.categories],
        )

        # Decide based on confidence
        if classification.level == SafetyLevel.UNCERTAIN:
            if self.fail_open:
                logger.warning("[LLMSafetyMiddleware] Uncertain classification, allowing (fail-open)")
                return True, None
            else:
                logger.warning("[LLMSafetyMiddleware] Uncertain classification, blocking (fail-closed)")
                return False, "[GUARDRAIL_INTERVENED] {\"code\":\"UNCERTAIN_SAFETY\"}"

        if not classification.is_safe:
            if classification.confidence >= self.confidence_threshold:
                logger.warning(
                    f"[LLMSafetyMiddleware] Input blocked: {classification.categories} "
                    f"(confidence: {classification.confidence:.2f})"
                )
                category_codes = "_".join([cat.value.upper() for cat in classification.categories[:2]])
                return False, f'[GUARDRAIL_INTERVENED] {{"code":"UNSAFE_INPUT_{category_codes}"}}'
            else:
                logger.info(
                    f"[LLMSafetyMiddleware] Low confidence unsafe ({classification.confidence:.2f}), allowing"
                )
                return True, None

        return True, None

    async def validate_output(
        self,
        text: str,
        user_context: dict = None
    ) -> tuple[bool, str | None]:
        """Validate output text from LLM.

        Args:
            text: Generated text to validate
            user_context: Optional user context

        Returns:
            (is_safe, violation_message)

        """
        if not text.strip():
            return True, None

        # Build context
        context = self._build_context(user_context, "output")

        # Classify
        classification = await self.classifier.classify(text, context)
        logger.info(
            "[LLMSafetyMiddleware][output] level=%s confidence=%.2f categories=%s",
            classification.level.value,
            classification.confidence,
            [cat.value for cat in classification.categories],
        )

        # Decide based on confidence
        if classification.level == SafetyLevel.UNCERTAIN:
            if self.fail_open:
                logger.warning("[LLMSafetyMiddleware] Uncertain output, allowing (fail-open)")
                return True, None
            else:
                logger.warning("[LLMSafetyMiddleware] Uncertain output, blocking (fail-closed)")
                return False, "UNCERTAIN_SAFETY"

        if not classification.is_safe:
            if classification.confidence >= self.confidence_threshold:
                logger.warning(
                    f"[LLMSafetyMiddleware] Output blocked: {classification.categories} "
                    f"(confidence: {classification.confidence:.2f})"
                )
                category_codes = "_".join([cat.value.upper() for cat in classification.categories[:2]])
                return False, f"UNSAFE_OUTPUT_{category_codes}"
            else:
                logger.info(
                    f"[LLMSafetyMiddleware] Low confidence unsafe ({classification.confidence:.2f}), allowing"
                )
                return True, None

        return True, None

    def _build_context(self, user_context: dict | None, direction: str) -> str:
        """Build context string for classification."""
        context_parts = []

        if user_context:
            if "blocked_topics" in user_context:
                topics = user_context["blocked_topics"]
                if topics:
                    context_parts.append(f"User has blocked topics: {', '.join(topics)}")

            if "preferences" in user_context:
                prefs = user_context["preferences"]
                context_parts.append(f"User preferences: {prefs}")

        context_parts.append(f"Validating {direction} for financial advisory chatbot")

        return ". ".join(context_parts)
