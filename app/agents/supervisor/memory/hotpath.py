from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import unicodedata
from json import JSONDecodeError
from typing import Any
from uuid import uuid4

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_store
from langgraph.graph import MessagesState

from app.core.app_state import get_sse_queue, get_bedrock_runtime_client
from app.core.config import config

from .profile_sync import _profile_sync_from_memory
from .utils import _build_profile_line, _parse_iso, _utc_now_iso

logger = logging.getLogger(__name__)


MODEL_ID = config.MEMORY_TINY_LLM_MODEL_ID
REGION = config.AWS_REGION
MERGE_TOPK = config.MEMORY_MERGE_TOPK
AUTO_UPDATE = config.MEMORY_MERGE_AUTO_UPDATE
CHECK_LOW = config.MEMORY_MERGE_CHECK_LOW
MERGE_MODE = config.MEMORY_MERGE_MODE.lower()
SEMANTIC_MIN_IMPORTANCE = config.MEMORY_SEMANTIC_MIN_IMPORTANCE
FALLBACK_ENABLED = config.MEMORY_MERGE_FALLBACK_ENABLED
FALLBACK_LOW = config.MEMORY_MERGE_FALLBACK_LOW
FALLBACK_TOPK = config.MEMORY_MERGE_FALLBACK_TOPK
FALLBACK_RECENCY_DAYS = config.MEMORY_MERGE_FALLBACK_RECENCY_DAYS
FALLBACK_CATEGORIES_RAW = config.MEMORY_MERGE_FALLBACK_CATEGORIES
FALLBACK_CATEGORIES = {c.strip() for c in FALLBACK_CATEGORIES_RAW.split(",") if c.strip()}


def _collect_recent_user_texts(messages: list[Any], max_messages: int = 3) -> list[str]:
    recent_user_texts: list[str] = []
    for m in reversed(messages):
        role = getattr(m, "role", getattr(m, "type", None))
        if role in ("user", "human"):
            content = getattr(m, "content", None)
            if isinstance(content, str) and content.strip():
                recent_user_texts.append(content.strip())
                if len(recent_user_texts) >= max_messages:
                    break
    return list(reversed(recent_user_texts))


def _trigger_decide(text: str) -> dict[str, Any]:
    bedrock = get_bedrock_runtime_client()
    allowed_categories = (
        "Finance, Budget, Goals, Personal, Education, Conversation_Summary, Other"
    )
    instr = (
        "You classify whether to CREATE a user memory from recent user messages.\n"
        "This node ONLY creates semantic memories (durable, re-usable facts).\n"
        "\n"
        "Semantic scope includes (non-exhaustive):\n"
        "- Identity & relationships: preferred name/pronouns; partner/family/pets; roles (student/parent/manager).\n"
        "- Stable attributes: age/birthday, home city/region, employer/school, time zone, languages.\n"
        "- Preferences & constraints: communication channel, tone, dietary, risk tolerance, price caps, brand/tool choices.\n"
        "- Long-term goals/plans: save for X, learn Y, travel Z, career targets.\n"
        "- Recurring routines/schedules: weekly reviews on Sundays, gym Tue/Thu.\n"
        "- Memberships/subscriptions/providers: bank, insurer, plan tiers.\n"
        "\n"
        "Rules:\n"
        "- If the user explicitly asks to 'remember' something, set should_create=true.\n"
        "- Create semantic if the message states OR UPDATES a stable fact about the user or close entities.\n"
        "- DO NOT create here for time-bound events/experiences or one-off actions (episodic handled later).\n"
        "- DO NOT create for meta/capability questions such as 'what do you know about me', 'do you remember me',\n"
        "  'what's in my profile', 'what have you saved about me'.\n"
        "- For the summary: NEVER include absolute dates or relative-time words (today, yesterday, this morning/afternoon/evening/tonight, last/next week/month/year, recently, soon).\n"
        "- If the input mixes time-bound details with a durable fact, EXTRACT ONLY the durable fact and DROP time phrasing.\n"
        "- Choose category from: [" + allowed_categories + "].\n"
        "- summary must be 1–2 sentences, concise and neutral (third person).\n"
        "- Output ONLY strict JSON: {\"should_create\": bool, \"type\": \"semantic\", \"category\": string, \"summary\": string, \"importance\": 1..5}.\n"
        "\n"
        "Examples (create):\n"
        "- Input: 'Please remember my name is Ana' -> {\"should_create\": true, \"type\": \"semantic\", \"category\": \"Personal\", \"summary\": \"User's preferred name is Ana.\", \"importance\": 2}\n"
        "- Input: 'My cat just turned 4 today' -> {\"should_create\": true, \"type\": \"semantic\", \"category\": \"Personal\", \"summary\": \"User's cat is 4 years old.\", \"importance\": 3}\n"
        "- Input: 'I prefer email over phone calls' -> {\"should_create\": true, \"type\": \"semantic\", \"category\": \"Personal\", \"summary\": \"User prefers email communication over calls.\", \"importance\": 2}\n"
        "- Input: 'We're saving for a house down payment this year' -> {\"should_create\": true, \"type\": \"semantic\", \"category\": \"Finance\", \"summary\": \"User is saving for a house down payment.\", \"importance\": 3}\n"
        "\n"
        "Examples (do not create here):\n"
        "- Input: 'We celebrated at the park today' -> {\"should_create\": false}\n"
        "- Input: 'Book an appointment' -> {\"should_create\": false}\n"
        "- Input: 'What do you know about me?' -> {\"should_create\": false}\n"
        "- Input: 'Do you remember me?' -> {\"should_create\": false}\n"
        "- Input: 'What have you saved in my profile?' -> {\"should_create\": false}\n"
    )
    prompt = f"{instr}\nRecentMessages:\n{text[:1000]}\nJSON:"
    try:
        body_payload = {
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"temperature": 0.0, "topP": 0.1, "maxTokens": 96, "stopSequences": []},
        }
        res = bedrock.invoke_model(modelId=MODEL_ID, body=json.dumps(body_payload))
        body = res.get("body")
        txt = body.read().decode("utf-8") if hasattr(body, "read") else str(body)
        data = json.loads(txt)
        out_text = ""
        try:
            contents = data.get("output", {}).get("message", {}).get("content", [])
            for part in contents:
                if isinstance(part, dict) and part.get("text"):
                    out_text += part.get("text", "")
        except Exception:
            out_text = ""
        if not out_text:
            out_text = data.get("outputText") or data.get("generation") or ""
        if not out_text:
            return {"should_create": False}
        try:
            out = json.loads(out_text)
        except Exception:
            i, j = out_text.find("{"), out_text.rfind("}")
            if i != -1 and j != -1 and j > i:
                out = json.loads(out_text[i:j+1])
            else:
                return {"should_create": False}
        if not isinstance(out, dict):
            return {"should_create": False}
        return out
    except (BotoCoreError, ClientError, JSONDecodeError, UnicodeDecodeError):
        logger.exception("trigger.error")
        return {"should_create": False}


def _search_neighbors(store: Any, namespace: tuple[str, ...], summary: str, category: str) -> list[Any]:
    try:
        neighbors = store.search(namespace, query=summary, filter={"category": category}, limit=MERGE_TOPK)
    except Exception:
        neighbors = []
    return neighbors


def _do_update(store: Any, namespace: tuple[str, ...], existing_key: str, summary: str, existing_item: Any | None = None) -> None:
    base_value: dict[str, Any] | None = None
    if existing_item is not None:
        try:
            base_value = dict(getattr(existing_item, "value", {}) or {})
        except Exception:
            base_value = None
    if base_value is None:
        existing = store.get(namespace, existing_key)
        if not existing:
            return
        base_value = dict(existing.value)
    merged = dict(base_value)
    merged["last_accessed"] = _utc_now_iso()
    if summary and len(summary) > len(merged.get("summary", "")):
        merged["summary"] = summary
    store.put(namespace, existing_key, merged, index=["summary"])  # re-embed


def _do_recreate(
    store: Any,
    namespace: tuple[str, ...],
    existing_key: str,
    existing_item: Any,
    summary: str,
    category: str,
    candidate_value: dict[str, Any],
) -> str:
    # Prefer using the neighbor's cached metadata to avoid an extra store.get
    existing_value: dict[str, Any] = dict(getattr(existing_item, "value", {}) or {})
    existing_summary = str(existing_value.get("summary") or "")
    composed = _compose_summaries(existing_summary, summary, category)
    new_id = uuid4().hex
    new_val = dict(candidate_value)
    new_val["id"] = new_id
    try:
        prev_imp = int(existing_value.get("importance") or 1)
    except Exception:
        prev_imp = 1
    new_val["importance"] = max(prev_imp, int(candidate_value.get("importance") or 1))
    new_val["pinned"] = bool(existing_value.get("pinned")) or bool(candidate_value.get("pinned"))
    try:
        prev_tags = existing_value.get("tags") or []
        cand_tags = candidate_value.get("tags") or []
        if isinstance(prev_tags, list) and isinstance(cand_tags, list):
            new_val["tags"] = list({*(t for t in prev_tags if isinstance(t, str)), *(t for t in cand_tags if isinstance(t, str))})
    except Exception:
        pass
    new_val["summary"] = composed
    store.put(namespace, new_id, new_val, index=["summary"])  # embed
    store.delete(namespace, existing_key)
    return new_id


async def _write_semantic_memory(
    user_id: str,
    thread_id: str | None,
    category: str,
    summary: str,
    candidate_value: dict[str, Any],
    mem_type: str,
    candidate_id: str,
) -> None:
    try:
        store = get_store()
        namespace = (user_id, "semantic")
        neighbors = _search_neighbors(store, namespace, summary, category)
        logger.info("memory.search: id=%s ns=%s neighbors=%d", candidate_id, "/".join(namespace), len(neighbors))

        best = neighbors[0] if neighbors else None
        did_update = False
        queue = get_sse_queue(thread_id) if thread_id else None
        sorted_neigh = sorted(neighbors, key=lambda it: float(getattr(it, "score", 0.0) or 0.0), reverse=True)
        if best and isinstance(getattr(best, "score", None), (int, float)):
            score_val = float(best.score or 0.0)
            recency_ok = True
            logger.info("memory.match: id=%s best_key=%s score=%.3f recency_ok=%s auto=%.2f low=%.2f", candidate_id, getattr(best, "key", ""), score_val, recency_ok, AUTO_UPDATE, CHECK_LOW)

            if score_val >= AUTO_UPDATE and recency_ok:
                if MERGE_MODE == "recreate":
                    _do_recreate(store, namespace, best.key, best, summary, category, candidate_value)
                    did_update = True
                    logger.info("memory.recreate: mode=auto id=%s from=%s score=%.3f", candidate_id, best.key, score_val)
                else:
                    _do_update(store, namespace, best.key, summary, best)
                    did_update = True
                    logger.info("memory.update: mode=auto id=%s into=%s score=%.3f", candidate_id, best.key, score_val)
                updated_memory = store.get(namespace, best.key)
                if queue and updated_memory:
                    with contextlib.suppress(Exception):
                        await queue.put({"event": "memory.updated", "data": {
                            "id": updated_memory.key,
                            "type": mem_type,
                            "category": (updated_memory.value or {}).get("category"),
                            "summary": (updated_memory.value or {}).get("summary"),
                            "importance": (updated_memory.value or {}).get("importance"),
                            "created_at": updated_memory.created_at,
                            "updated_at": updated_memory.updated_at,
                            "value": updated_memory.value
                        }})
            else:
                for n in sorted_neigh:
                    s = float(getattr(n, "score", 0.0) or 0.0)
                    if s < CHECK_LOW:
                        break
                    same = _same_fact_classify(
                        existing_summary=str((getattr(n, "value", {}) or {}).get("summary", "")),
                        candidate_summary=summary,
                        category=category,
                    )
                    logger.info("memory.classify: id=%s cand_into=%s score=%.3f result_same=%s", candidate_id, getattr(n, "key", ""), s, same)
                    if same:
                        if MERGE_MODE == "recreate":
                            _do_recreate(store, namespace, getattr(n, "key", ""), n, summary, category, candidate_value)
                            logger.info("memory.recreate: mode=classified id=%s from=%s", candidate_id, getattr(n, "key", ""))
                        else:
                            _do_update(store, namespace, getattr(n, "key", ""), summary, n)
                            logger.info("memory.update: mode=classified id=%s into=%s", candidate_id, getattr(n, "key", ""))
                        did_update = True
                        updated_memory = store.get(namespace, getattr(n, "key", ""))
                        if queue and updated_memory:
                            with contextlib.suppress(Exception):
                                await queue.put({"event": "memory.updated", "data": {
                                    "id": updated_memory.key,
                                    "type": mem_type,
                                    "category": (updated_memory.value or {}).get("category"),
                                    "summary": (updated_memory.value or {}).get("summary"),
                                    "importance": (updated_memory.value or {}).get("importance"),
                                    "created_at": updated_memory.created_at,
                                    "updated_at": updated_memory.updated_at,
                                    "value": updated_memory.value
                                }})
                        break
        if not did_update and FALLBACK_ENABLED and (not FALLBACK_CATEGORIES or category in FALLBACK_CATEGORIES):
            checked = 0
            for n in sorted_neigh:
                if checked >= max(1, FALLBACK_TOPK):
                    break
                s = float(getattr(n, "score", 0.0) or 0.0)
                if s < FALLBACK_LOW or s >= CHECK_LOW:
                    continue
                ts = _parse_iso(getattr(n, "updated_at", "")) or _parse_iso(getattr(n, "created_at", ""))
                recent_ok = True
                try:
                    if ts is not None:
                        from datetime import datetime, timezone
                        age_days = (datetime.now(tz=timezone.utc) - ts).days
                        recent_ok = age_days <= max(1, FALLBACK_RECENCY_DAYS)
                except Exception:
                    recent_ok = True
                ex_sum = str((getattr(n, "value", {}) or {}).get("summary", ""))
                lex_ok = _has_min_token_overlap(ex_sum, summary)
                num_ok = _numeric_overlap_or_step(ex_sum, summary)
                if not recent_ok or (not lex_ok and not num_ok):
                    continue
                same = _same_fact_classify(
                    existing_summary=ex_sum,
                    candidate_summary=summary,
                    category=category,
                )
                logger.info(
                    "memory.fallback.classify: id=%s cand_into=%s score=%.3f recent_ok=%s lex_ok=%s num_ok=%s result_same=%s",
                    candidate_id,
                    getattr(n, "key", ""),
                    s,
                    recent_ok,
                    lex_ok,
                    num_ok,
                    same,
                )
                checked += 1
                if same:
                    if MERGE_MODE == "recreate":
                        _do_recreate(store, namespace, getattr(n, "key", ""), n, summary, category, candidate_value)
                        logger.info("memory.recreate: mode=fallback id=%s from=%s", candidate_id, getattr(n, "key", ""))
                    else:
                        _do_update(store, namespace, getattr(n, "key", ""), summary, n)
                        logger.info("memory.update: mode=fallback id=%s into=%s", candidate_id, getattr(n, "key", ""))
                    did_update = True
                    updated_memory = store.get(namespace, getattr(n, "key", ""))
                    if queue and updated_memory:
                        with contextlib.suppress(Exception):
                            await queue.put({"event": "memory.updated", "data": {
                                "id": updated_memory.key,
                                "type": mem_type,
                                "category": (updated_memory.value or {}).get("category"),
                                "summary": (updated_memory.value or {}).get("summary"),
                                "importance": (updated_memory.value or {}).get("importance"),
                                "created_at": updated_memory.created_at,
                                "updated_at": updated_memory.updated_at,
                                "value": updated_memory.value
                            }})
                    break
        if not did_update:
            if int(candidate_value.get("importance") or 1) < SEMANTIC_MIN_IMPORTANCE:
                logger.info("memory.skip: below_min_importance=%s", SEMANTIC_MIN_IMPORTANCE)
            else:
                store.put(namespace, candidate_value["id"], candidate_value, index=["summary"])  # async context
                logger.info("memory.create: id=%s type=%s category=%s", candidate_value["id"], "semantic", category)

                asyncio.create_task(_profile_sync_from_memory(user_id, thread_id, candidate_value))
                if queue:
                    with contextlib.suppress(Exception):
                        await queue.put({"event": "memory.created", "data": {
                            "id": candidate_value["id"],
                            "type": mem_type,
                            "category": category,
                            "summary": candidate_value.get("summary"),
                            "importance": candidate_value.get("importance"),
                            "created_at": candidate_value.get("created_at"),
                            "updated_at": candidate_value.get("updated_at"),
                            "value": candidate_value
                        }})
    except Exception:
        logger.exception("memory_hotpath.error: id=%s", candidate_value.get("id"))
        if thread_id:
            try:
                queue = get_sse_queue(thread_id)
                await queue.put({"event": "memory.error", "data": {"id": candidate_value.get("id")}})
            except Exception:
                pass
def _same_fact_classify(existing_summary: str, candidate_summary: str, category: str) -> bool:
    bedrock = get_bedrock_runtime_client()
    prompt = (
        "Same-Fact Classifier (language-agnostic)\n"
        "Your job: Return whether two short summaries express the SAME underlying fact about the user.\n"
        "Decide by meaning, not wording. Ignore casing, punctuation, and minor phrasing differences.\n"
        "\n"
        "Core rules\n"
        "1) Same subject: Treat these as the same subject: exact same name (e.g., Luna), or clear role synonyms\n"
        "   (pet/cat/dog; spouse/partner/wife/husband; kid/child/son/daughter).\n"
        "2) Same attribute: If both describe the same attribute (e.g., age in years, relationship/name, number of kids),\n"
        "   then they are the SAME FACT even if phrased differently.\n"
        "3) Numeric updates: If the attribute is numeric or count-like and changes plausibly (e.g., 3→4 years), treat as\n"
        "   the SAME FACT (updated value).\n"
        "4) Different entities: If the named entities differ (e.g., Luna vs Bruno) for the same attribute, NOT the same.\n"
        "5) Preference contradictions: Opposite preferences (e.g., prefers email vs prefers phone) are NOT the same.\n"
        "6) Episodic vs stable: One-off events vs stable facts are NOT the same.\n"
        "7) Multilingual: Treat cross-language synonyms as equivalent (e.g., 'español' == 'Spanish').\n"
        "\n"
        "Examples\n"
        "- 'Luna is 3 years old.' vs 'Luna is 4 years old.' -> same_fact=true (numeric update)\n"
        "- 'User's spouse is Natalia.' vs 'User's partner is Natalia.' -> same_fact=true (synonyms, same person)\n"
        "- 'Has two children.' vs 'Has 2 kids.' -> same_fact=true (synonyms, same count)\n"
        "- 'User prefers email.' vs 'User prefers phone calls.' -> same_fact=false (contradictory preference)\n"
        "- 'Lives in Austin.' vs 'Moved to Dallas.' -> same_fact=false (different locations, not a numeric update)\n"
        "- 'Luna is a cat.' vs 'Luna is a dog.' -> same_fact=false (conflicting species)\n"
        "\n"
        "Output: Return STRICT JSON only: {\"same_fact\": true|false}. No extra text.\n"
        f"Category: {category[:64]}\n"
        f"Existing: {existing_summary[:500]}\n"
        f"Candidate: {candidate_summary[:500]}\n"
    )
    try:
        body_payload = {
            "messages": [
                {"role": "user", "content": [{"text": prompt}]}
            ],
            "inferenceConfig": {"temperature": 0.0, "topP": 0.1, "maxTokens": 128, "stopSequences": []},
        }
        res = bedrock.invoke_model(modelId=MODEL_ID, body=json.dumps(body_payload))
        body = res.get("body")
        txt = body.read().decode("utf-8") if hasattr(body, "read") else str(body)
        data = json.loads(txt)
        out_text = ""
        try:
            contents = data.get("output", {}).get("message", {}).get("content", [])
            for part in contents:
                if isinstance(part, dict) and part.get("text"):
                    out_text += part.get("text", "")
        except Exception:
            out_text = ""
        if not out_text:
            out_text = data.get("outputText") or data.get("generation") or ""
        if not out_text:
            return False
        try:
            out = json.loads(out_text)
        except Exception:
            i, j = out_text.find("{"), out_text.rfind("}")
            if i != -1 and j != -1 and j > i:
                out = json.loads(out_text[i:j+1])
            else:
                return False
        return bool(out.get("same_fact") is True)
    except Exception:
        logger.exception("same_fact.error")
        return False


def _compose_summaries(existing_summary: str, candidate_summary: str, category: str) -> str:
    bedrock = get_bedrock_runtime_client()
    prompt = (
        "Task: Combine two short summaries about the SAME user fact into one concise statement.\n"
        "- Keep it neutral, third person, and include both details without redundancy.\n"
        "- 1–2 sentences, max 280 characters.\n"
        "- Do NOT include absolute dates or relative-time words (today, yesterday, this morning/afternoon/evening/tonight, last/next week/month/year, recently, soon).\n"
        "- Express the timeless fact only.\n"
        "Output ONLY the composed text.\n"
        f"Category: {category[:64]}\n"
        f"Existing: {existing_summary[:500]}\n"
        f"New: {candidate_summary[:500]}\n"
    )
    try:
        body_payload = {
            "messages": [
                {"role": "user", "content": [{"text": prompt}]}
            ],
            "inferenceConfig": {"temperature": 0.2, "topP": 0.5, "maxTokens": 160, "stopSequences": []},
        }
        res = bedrock.invoke_model(modelId=MODEL_ID, body=json.dumps(body_payload))
        body = res.get("body")
        txt = body.read().decode("utf-8") if hasattr(body, "read") else str(body)
        data = json.loads(txt)
        out_text = ""
        try:
            contents = data.get("output", {}).get("message", {}).get("content", [])
            for part in contents:
                if isinstance(part, dict) and part.get("text"):
                    out_text += part.get("text", "")
        except Exception:
            out_text = ""
        if not out_text:
            out_text = data.get("outputText") or data.get("generation") or ""
        composed = (out_text or "").strip()
        if not composed:
            raise ValueError("empty compose")
        return composed[:280]
    except Exception:
        a = (existing_summary or "").strip()
        b = (candidate_summary or "").strip()
        if not a:
            return b[:280]
        if not b:
            return a[:280]
        if a.lower() in b.lower():
            return b[:280]
        if b.lower() in a.lower():
            return a[:280]
        return f"{a} {b}"[:280]


def _normalize_summary_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    # Normalize Unicode and replace smart quotes to prevent mojibake (e.g., \u2019)
    t = unicodedata.normalize("NFC", text)
    t = (
        t.replace("\u2019", "'")
         .replace("\u2018", "'")
         .replace("\u201C", '"')
         .replace("\u201D", '"')
    )
    return t


# Combined regex pattern for time sanitization (single pass)
_TIME_SANITIZATION_PATTERN = re.compile(
    r"\b(today|yesterday|tomorrow|this\s+(morning|afternoon|evening|tonight)|"
    r"(last|next)\s+(week|month|year)|recently|soon|earlier|later|now)\b|"
    r"\bon\s+\d{4}-\d{2}-\d{2}\b|\bthis\s+year\b",
    re.IGNORECASE
)

# Cleanup patterns for whitespace and punctuation
_CLEANUP_PATTERNS = [
    (re.compile(r"\s{2,}"), " "),
    (re.compile(r"\s+,"), ","),
    (re.compile(r"\(\s*\)"), ""),
]


def _sanitize_semantic_time_phrases(text: str) -> str:
    """Sanitize semantic time phrases from text for better memory storage.

    Uses a single-pass regex pattern to remove time-related phrases efficiently,
    minimizing intermediate string creation for optimal performance.
    """
    if not isinstance(text, str):
        return ""

    sanitized = _TIME_SANITIZATION_PATTERN.sub("", text)

    for pattern, repl in _CLEANUP_PATTERNS:
        sanitized = pattern.sub(repl, sanitized)

    return sanitized.strip()

def _has_min_token_overlap(a: str, b: str) -> bool:
    # Very light lexical guard: share at least one non-stopword token (len>=3)
    def toks(s: str) -> set[str]:
        raw = re.findall(r"[\w\-\p{L}]+", s, flags=re.UNICODE)
        # Fallback for engines without \p{L}
        if not raw:
            raw = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9_\-]+", s)
        return {t.lower() for t in raw if len(t) >= 3}

    try:
        ta = toks(a)
        tb = toks(b)
        return bool(ta.intersection(tb))
    except Exception:
        return False


def _numeric_overlap_or_step(a: str, b: str) -> bool:
    try:
        na = {int(x) for x in re.findall(r"\d+", a)}
        nb = {int(x) for x in re.findall(r"\d+", b)}
        if not na and not nb:
            return False
        if na.intersection(nb):
            return True
        for x in na:
            for y in nb:
                if abs(x - y) == 1:
                    return True
        return False
    except Exception:
        return False


async def memory_hotpath(state: MessagesState, config: RunnableConfig) -> dict:
    messages = state["messages"]
    recent_user_texts = _collect_recent_user_texts(messages, max_messages=3)
    if not recent_user_texts:
        return {}
    combined_text = "\n".join(recent_user_texts)

    trigger = _trigger_decide(combined_text)
    logger.info(
        "memory.decide: should_create=%s type=%s category=%s importance=%s",
        bool(trigger.get("should_create")),
        str(trigger.get("type") or "").lower(),
        str(trigger.get("category") or ""),
        trigger.get("importance"),
    )
    if not trigger.get("should_create"):
        ctx = config.get("configurable", {}).get("user_context") or {}
        prof = _build_profile_line(ctx) if isinstance(ctx, dict) else None
        return {"messages": [HumanMessage(content=prof)]} if prof else {}

    thread_id = config.get("configurable", {}).get("thread_id")
    user_id = config.get("configurable", {}).get("user_id")
    if not user_id:
        return {}

    mem_type = str(trigger.get("type") or "semantic").lower()
    if mem_type not in ("semantic", "episodic"):
        mem_type = "semantic"
    category = str(trigger.get("category") or "Other").replace(" ", "_")
    if category not in {"Finance", "Budget", "Goals", "Personal", "Education", "Conversation_Summary", "Other"}:
        category = "Other"
    summary_raw = str(trigger.get("summary") or recent_user_texts[0] or combined_text).strip()[:280]
    summary = _normalize_summary_text(summary_raw)
    summary = _sanitize_semantic_time_phrases(summary)

    if mem_type != "semantic":
        logger.info("memory.skip: entry node only writes semantic; type=%s", mem_type)
        ctx = config.get("configurable", {}).get("user_context") or {}
        prof = _build_profile_line(ctx) if isinstance(ctx, dict) else None
        return ({"messages": [HumanMessage(content=prof)]} if prof else {})

    candidate_id = uuid4().hex
    now = _utc_now_iso()
    candidate_value: dict[str, Any] = {
        "id": candidate_id,
        "user_id": user_id,
        "type": "semantic",
        "summary": summary,
        "category": category,
        "tags": [],
        "source": "chat",
        "importance": int(trigger.get("importance") or 1),
        "pinned": False,
        "created_at": now,
        "last_accessed": now,
    }
    logger.info(
        "memory_hotpath.candidate: id=%s type=%s category=%s summary_preview=%s",
        candidate_id,
        mem_type,
        category,
        (summary[:80] + ("…" if len(summary) > 80 else "")),
    )

    if int(candidate_value.get("importance") or 1) >= SEMANTIC_MIN_IMPORTANCE and thread_id:
        try:
            queue = get_sse_queue(thread_id)
            await queue.put({"event": "memory.created", "data": {"id": candidate_id, "type": mem_type, "category": category, "summary": summary}})
        except Exception:
            pass

    asyncio.create_task(_write_semantic_memory(
        user_id=user_id,
        thread_id=thread_id,
        category=category,
        summary=summary,
        candidate_value=candidate_value,
        mem_type=mem_type,
        candidate_id=candidate_id,
    ))
    ctx = config.get("configurable", {}).get("user_context") or {}
    prof = _build_profile_line(ctx) if isinstance(ctx, dict) else None
    return ({"messages": [HumanMessage(content=prof)]} if prof else {})


