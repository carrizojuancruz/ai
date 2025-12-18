from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import MessagesState
from langgraph.types import RunnableConfig

from app.core.config import config
from app.services.llm.prompt_loader import prompt_loader
from app.services.llm.safe_cerebras import SafeChatCerebras

logger = logging.getLogger(__name__)

# High threshold required for smalltalk confirmation (conservative)
SMALLTALK_CONFIDENCE_THRESHOLD: float = 0.90

# Maximum word count for messages that could be pure smalltalk
SMALLTALK_MAX_WORDS: int = 12

# Confidence values for different veto reasons
TASK_MARKER_VETO_CONFIDENCE: float = 0.95
STRUCTURAL_VETO_CONFIDENCE: float = 0.90
LENGTH_VETO_CONFIDENCE: float = 0.85

# LLM classification timeout in seconds
LLM_CLASSIFICATION_TIMEOUT: float = 3.0

CLASSIFIER_PROMPT: str = prompt_loader.load("intent_classifier_routing_prompt")

TASK_VETO_MARKERS: tuple[str, ...] = (
    # Finance-related (comprehensive)
    "balance",
    "spend",
    "spent",
    "spending",
    "budget",
    "saving",
    "savings",
    "invest",
    "investing",
    "investment",
    "credit",
    "account",
    "accounts",
    "transaction",
    "transactions",
    "charge",
    "charges",
    "income",
    "paycheck",
    "expense",
    "expenses",
    "bill",
    "bills",
    "payment",
    "payments",
    "refund",
    "receipt",
    "merchant",
    "dining",
    "groceries",
    "net worth",
    "networth",
    "assets",
    "asset",
    "liabilities",
    "liability",
    "debt",
    "debts",
    "loan",
    "loans",
    "mortgage",
    "transfer",
    "withdraw",
    "deposit",
    # Goal-related
    "goal",
    "goals",
    "target",
    "targets",
    "habit",
    "habits",
    "track",
    "tracking",
    "save for",
    "saving for",
    # Query patterns
    "how much",
    "how many",
    "when was the last",
    "when did i",
    "last time",
    "show me",
    "list my",
    "view my",
    "where is",
    "how do i",
    "what is my",
    "what's my",
    "whats my",
    "check my",
    "tell me about my",
    # App/settings patterns
    "settings",
    "setting",
    "feature",
    "features",
    "toggle",
    "enable",
    "disable",
    "configure",
    "configuration",
    # Action patterns
    "add",
    "record",
    "log",
    "upload",
    "connect account",
    "link account",
    "unlink",
    "delete account",
    "create",
    "update",
    "change",
    "modify",
    "edit",
    "remove",
    "delete",
    "set up",
    "setup",
    # Help/question patterns (critical for catching implicit tasks)
    "help me",
    "can you help",
    "could you help",
    "would you help",
    "i need to",
    "i want to",
    "i'd like to",
    "i need",
    "i want",
    "quick question",
    "have a question",
    "got a question",
    "a question",
    "what can you do",
    "what do you do",
    "your features",
    "your capabilities",
    "what are you capable",
    # Request starters
    "could you",
    "would you",
    "can you",
    "will you",
    "please check",
    "please show",
    "please help",
    "please tell",
    "please update",
    "please add",
)


def _extract_user_text(state: MessagesState) -> str:
    messages = state.get("messages") or []
    for message in reversed(messages):
        role = getattr(message, "role", getattr(message, "type", None))
        if role in ("user", "human"):
            content = getattr(message, "content", "")
            if isinstance(content, str):
                return content.strip()
    return ""


def _supervisor_result(label: str, confidence: float) -> dict[str, Any]:
    return {
        "intent_route": "supervisor",
        "intent_classifier_label": label,
        "intent_classifier_confidence": confidence,
    }


def _fast_result(confidence: float) -> dict[str, Any]:
    return {
        "intent_route": "fast",
        "intent_classifier_label": "smalltalk",
        "intent_classifier_confidence": confidence,
    }


def _has_task_markers(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(marker in lowered for marker in TASK_VETO_MARKERS)


def _has_structural_task_patterns(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower().strip()
    words = lowered.split()

    if not words:
        return False

    is_question = lowered.rstrip().endswith("?")
    question_starters = (
        "what",
        "when",
        "where",
        "why",
        "how",
        "which",
        "who",
        "can",
        "could",
        "would",
        "will",
        "do",
        "does",
        "did",
        "is",
        "are",
        "have",
        "has",
    )
    starts_with_question_word = words[0] in question_starters

    if (is_question or starts_with_question_word) and " my " in lowered:
        return True

    if starts_with_question_word and words[0] == "what" and len(words) >= 2 and words[1] in ("can", "do", "are", "is"):
        return True

    imperative_verbs = (
        "show",
        "tell",
        "explain",
        "check",
        "update",
        "change",
        "create",
        "delete",
        "add",
        "remove",
        "set",
        "get",
        "find",
        "list",
        "view",
        "give",
        "make",
        "help",
        "let",
    )
    if words[0] in imperative_verbs:
        return True

    if len(words) >= 2 and words[0] == "i" and words[1] in ("need", "want", "have"):
        has_smalltalk_continuation = len(words) >= 3 and words[2] in ("nothing", "no")
        return not has_smalltalk_continuation

    return False


def _is_message_too_complex(text: str) -> bool:
    if not text:
        return False
    word_count = len(text.split())
    return word_count > SMALLTALK_MAX_WORDS


async def _classify_with_llm(text: str) -> tuple[str, float]:
    llm = SafeChatCerebras(
        model=config.FAST_PATH_MODEL_ID,
        api_key=config.CEREBRAS_API_KEY,
        temperature=0.0,
        input_config={
            "use_llm_classifier": True,
            "llm_confidence_threshold": config.INTENT_CLASSIFIER_CONFIDENCE_THRESHOLD,
            "enabled_checks": ["injection", "pii", "blocked_topics", "internal_exposure"],
        },
        output_config={
            "use_llm_classifier": False,
            "enabled_checks": ["pii_leakage", "context_exposure", "internal_exposure"],
        },
        user_context={"blocked_topics": []},
        fail_open=True,
    )
    try:
        result = await llm.ainvoke(
            [SystemMessage(content=CLASSIFIER_PROMPT), HumanMessage(content=text)],
        )
        content = getattr(result, "content", "")
        parsed: dict[str, Any] = {}
        if isinstance(content, str):
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                logger.warning("intent_classifier.llm.json_parse_error content=%s", content[:100])
                return "unknown", 0.0
        intent = str(parsed.get("intent", "unknown")).lower()
        confidence = float(parsed.get("confidence", 0.0)) if parsed else 0.0
        return intent, confidence
    except Exception as exc:  # noqa: BLE001
        logger.warning("intent_classifier.llm.error err=%s", exc)
        return "unknown", 0.0


async def _classify_with_llm_safe(text: str) -> tuple[str, float]:
    try:
        return await asyncio.wait_for(
            _classify_with_llm(text),
            timeout=LLM_CLASSIFICATION_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning("intent_classifier.llm.timeout seconds=%.1f", LLM_CLASSIFICATION_TIMEOUT)
        return "supervisor", 0.0
    except Exception as exc:  # noqa: BLE001
        logger.warning("intent_classifier.llm.unexpected_error err=%s", exc)
        return "supervisor", 0.0


def _post_classification_sanity_check(text: str, llm_intent: str, llm_confidence: float) -> tuple[str, float]:
    if llm_intent != "smalltalk":
        return llm_intent, llm_confidence

    lowered = text.lower()

    if "?" in text:
        simple_questions = (
            "how are you",
            "what's up",
            "whats up",
            "how is it going",
            "how's it going",
            "how you doing",
            "what is up",
            "how do you do",
            "you good",
            "you okay",
        )
        is_simple_question = any(q in lowered for q in simple_questions)
        has_task_words = any(word in lowered for word in (" my ", " i ", "account", "money", "spend"))
        if not is_simple_question and has_task_words:
            logger.info("intent_classifier.sanity_check.override reason=question_with_task_words")
            return "supervisor", 0.5

    has_need_want = any(pattern in lowered for pattern in ("i need", "i want", "i'd like", "i have to"))
    has_smalltalk_continuation = any(st in lowered for st in ("nothing", "no one", "nobody", "just chat", "just talk"))
    if has_need_want and not has_smalltalk_continuation:
        logger.info("intent_classifier.sanity_check.override reason=need_want_pattern")
        return "supervisor", 0.5

    return llm_intent, llm_confidence


async def intent_classifier(
    state: MessagesState,
    run_config: RunnableConfig | None = None,  # noqa: ARG001
) -> dict[str, Any]:
    if not config.FAST_PATH_ENABLED:
        return {"intent_route": "supervisor"}

    user_text = _extract_user_text(state)
    if not user_text:
        return {"intent_route": "supervisor"}

    if _has_task_markers(user_text):
        logger.info(
            "intent_classifier.veto gate=task_markers text_preview=%s",
            user_text[:80],
        )
        return _supervisor_result("task_marker_veto", TASK_MARKER_VETO_CONFIDENCE)

    if _has_structural_task_patterns(user_text):
        logger.info(
            "intent_classifier.veto gate=structural_pattern text_preview=%s",
            user_text[:80],
        )
        return _supervisor_result("structural_veto", STRUCTURAL_VETO_CONFIDENCE)

    if _is_message_too_complex(user_text):
        logger.info(
            "intent_classifier.veto gate=message_length words=%d text_preview=%s",
            len(user_text.split()),
            user_text[:80],
        )
        return _supervisor_result("length_veto", LENGTH_VETO_CONFIDENCE)

    intent_llm, conf_llm = await _classify_with_llm_safe(user_text)

    intent_final, conf_final = _post_classification_sanity_check(user_text, intent_llm, conf_llm)

    if intent_final == "smalltalk" and conf_final >= SMALLTALK_CONFIDENCE_THRESHOLD:
        logger.info(
            "intent_classifier.fast_confirmed confidence=%.2f text_preview=%s",
            conf_final,
            user_text[:80],
        )
        return _fast_result(conf_final)

    logger.info(
        "intent_classifier.supervisor_fallback "
        "llm_intent=%s llm_conf=%.2f final_intent=%s final_conf=%.2f text_preview=%s",
        intent_llm,
        conf_llm,
        intent_final,
        conf_final,
        user_text[:80],
    )
    return _supervisor_result(intent_final or "uncertain", conf_final)
