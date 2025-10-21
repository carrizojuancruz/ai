from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import time
import unicodedata
from json import JSONDecodeError
from typing import Any
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_store
from langgraph.graph import MessagesState

from app.core.app_state import get_bedrock_runtime_client, get_sse_queue
from app.core.config import config
from app.utils.tools import get_config_value

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
    allowed_categories = "Finance, Budget, Goals, Personal, Education, Conversation_Summary, Other"
    instr = (
        "You classify whether to CREATE a user memory from recent user messages.\n"
        "This node ONLY creates semantic memories (durable, re-usable facts).\n"
        "\n"
        "Semantic scope includes (non-exhaustive):\n"
        "- Identity & relationships: preferred name/pronouns; partner/family/pets; roles (student/parent/manager).\n"
        "- Stable attributes: age/birthday, home city/region, employer/school, time zone, languages.\n"
        "- Preferences & constraints: communication channel, tone, dietary, risk tolerance, price caps, brand/tool choices.\n"
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
        '- Output ONLY strict JSON: {"should_create": bool, "type": "semantic", "category": string, "summary": string, "importance": 1..5}.\n'
        "\n"
        "AUTHORITATIVE DOMAINS POLICY — NEVER create semantic memories for facts owned by specialized agents:\n"
        "- Finance (Plaid/SQL): budgets, balances, account details, transaction totals, spending amounts/trends, bills due, interest rates.\n"
        "- Goals system: goal targets/amounts/percentages, dates/timelines, statuses (in_progress/completed/etc.).\n"
        "- Wealth knowledge: investment returns/rules, financial program/tax rules, general financial facts.\n"
        "If the input asserts a numeric financial value or any detail above, return {\"should_create\": false}.\n"
        "Even if the user says 'remember ...', still return {\"should_create\": false} for these domains.\n"
        "\n"
        "Examples (create):\n"
        '- Input: \'Please remember my name is Ana\' -> {"should_create": true, "type": "semantic", "category": "Personal", "summary": "User\'s preferred name is Ana.", "importance": 2}\n'
        '- Input: \'My cat just turned 4 today\' -> {"should_create": true, "type": "semantic", "category": "Personal", "summary": "User\'s cat is 4 years old.", "importance": 3}\n'
        '- Input: \'I prefer email over phone calls\' -> {"should_create": true, "type": "semantic", "category": "Personal", "summary": "User prefers email communication over calls.", "importance": 2}\n'
        '- Input: \'We\'re saving for a house down payment this year\' -> {"should_create": true, "type": "semantic", "category": "Finance", "summary": "User is saving for a house down payment.", "importance": 3}\n'
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
        t0 = time.perf_counter()
        logger.info("memory.llm.trigger.start model=%s text_len=%d", MODEL_ID, len(text or ""))
        body_payload = {
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"temperature": 0.0, "topP": 0.1, "maxTokens": 96, "stopSequences": []},
        }
        res = bedrock.invoke_model(modelId=MODEL_ID, body=json.dumps(body_payload))
        t1 = time.perf_counter()
        logger.info("memory.llm.trigger.done ms=%d", int((t1 - t0) * 1000))
        body = res.get("body")
        txt = body.read().decode("utf-8") if hasattr(body, "read") else str(body)
        data = json.loads(txt)
        out_text = ""
        try:
            contents = data.get("output", {}).get("message", {}).get("content", "")
            if isinstance(contents, list):
                for part in contents:
                    if isinstance(part, dict) and part.get("text"):
                        out_text += part.get("text", "")
            elif isinstance(contents, str):
                out_text = contents
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
                out = json.loads(out_text[i : j + 1])
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
        t0 = time.perf_counter()
        ns0_present = bool(namespace and namespace[0])
        ns1 = namespace[1] if len(namespace) > 1 else ""
        logger.info(
            "memory.store.search.start ns0_set=%s ns1=%s topk=%d has_filter=%s",
            ns0_present,
            ns1,
            MERGE_TOPK,
            True,
        )
        neighbors = store.search(namespace, query=summary, filter={"category": category}, limit=MERGE_TOPK)
        t1 = time.perf_counter()
        logger.info("memory.store.search.done ms=%d results=%d", int((t1 - t0) * 1000), len(neighbors or []))
    except Exception:
        logger.exception("memory.store.search.error")
        neighbors = []
    return neighbors


def _do_update(
    store: Any, namespace: tuple[str, ...], existing_key: str, summary: str, existing_item: Any | None = None
) -> None:
    base_value: dict[str, Any] | None = None
    if existing_item is not None:
        try:
            base_value = dict(getattr(existing_item, "value", {}) or {})
        except Exception:
            base_value = None
    if base_value is None:
        t0g = time.perf_counter()
        ns0_present = bool(namespace and namespace[0])
        ns1 = namespace[1] if len(namespace) > 1 else ""
        logger.info("memory.store.get.start ns0_set=%s ns1=%s", ns0_present, ns1)
        existing = store.get(namespace, existing_key)
        t1g = time.perf_counter()
        logger.info("memory.store.get.done ms=%d found=%s", int((t1g - t0g) * 1000), bool(existing))
        if not existing:
            return
        base_value = dict(existing.value)
    merged = dict(base_value)
    merged["last_accessed"] = _utc_now_iso()
    if summary and len(summary) > len(merged.get("summary", "")):
        merged["summary"] = summary
    t0p = time.perf_counter()
    logger.info("memory.store.put.start ns0_set=%s ns1=%s mode=update", ns0_present, ns1)
    store.put(namespace, existing_key, merged, index=["summary"])  # re-embed
    t1p = time.perf_counter()
    logger.info("memory.store.put.done ms=%d", int((t1p - t0p) * 1000))


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
            new_val["tags"] = list(
                {*(t for t in prev_tags if isinstance(t, str)), *(t for t in cand_tags if isinstance(t, str))}
            )
    except Exception:
        pass
    new_val["summary"] = composed
    ns0_present = bool(namespace and namespace[0])
    ns1 = namespace[1] if len(namespace) > 1 else ""
    t0p = time.perf_counter()
    logger.info("memory.store.put.start ns0_set=%s ns1=%s mode=recreate", ns0_present, ns1)
    store.put(namespace, new_id, new_val, index=["summary"])  # embed
    t1p = time.perf_counter()
    logger.info("memory.store.put.done ms=%d", int((t1p - t0p) * 1000))
    t0d = time.perf_counter()
    logger.info("memory.store.delete.start ns0_set=%s ns1=%s", ns0_present, ns1)
    store.delete(namespace, existing_key)
    t1d = time.perf_counter()
    logger.info("memory.store.delete.done ms=%d", int((t1d - t0d) * 1000))
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
            logger.info(
                "memory.match: id=%s best_key=%s score=%.3f recency_ok=%s auto=%.2f low=%.2f",
                candidate_id,
                getattr(best, "key", ""),
                score_val,
                recency_ok,
                AUTO_UPDATE,
                CHECK_LOW,
            )

            if score_val >= AUTO_UPDATE and recency_ok:
                updated_key = None
                if MERGE_MODE == "recreate":
                    new_id = _do_recreate(store, namespace, best.key, best, summary, category, candidate_value)
                    did_update = True
                    logger.info(
                        "memory.recreate: mode=auto id=%s from=%s score=%.3f", candidate_id, best.key, score_val
                    )
                    updated_key = new_id
                else:
                    _do_update(store, namespace, best.key, summary, best)
                    did_update = True
                    logger.info("memory.update: mode=auto id=%s into=%s score=%.3f", candidate_id, best.key, score_val)
                    updated_key = best.key
                updated_memory = store.get(namespace, updated_key)
                if updated_memory:
                    asyncio.create_task(_profile_sync_from_memory(user_id, thread_id, updated_memory.value))
                if queue and updated_memory:
                    with contextlib.suppress(Exception):
                        await queue.put(
                            {
                                "event": "memory.updated",
                                "data": {
                                    "id": updated_memory.key,
                                    "type": mem_type,
                                    "category": (updated_memory.value or {}).get("category"),
                                    "summary": (updated_memory.value or {}).get("summary"),
                                    "importance": (updated_memory.value or {}).get("importance"),
                                    "created_at": updated_memory.created_at,
                                    "updated_at": updated_memory.updated_at,
                                    "value": updated_memory.value,
                                },
                            }
                        )
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
                    logger.info(
                        "memory.classify: id=%s cand_into=%s score=%.3f result_same=%s",
                        candidate_id,
                        getattr(n, "key", ""),
                        s,
                        same,
                    )
                    if same:
                        if MERGE_MODE == "recreate":
                            _do_recreate(store, namespace, getattr(n, "key", ""), n, summary, category, candidate_value)
                            logger.info(
                                "memory.recreate: mode=classified id=%s from=%s", candidate_id, getattr(n, "key", "")
                            )
                        else:
                            _do_update(store, namespace, getattr(n, "key", ""), summary, n)
                            logger.info(
                                "memory.update: mode=classified id=%s into=%s", candidate_id, getattr(n, "key", "")
                            )
                        did_update = True
                        updated_memory = store.get(namespace, getattr(n, "key", ""))
                        if queue and updated_memory:
                            with contextlib.suppress(Exception):
                                await queue.put(
                                    {
                                        "event": "memory.updated",
                                        "data": {
                                            "id": updated_memory.key,
                                            "type": mem_type,
                                            "category": (updated_memory.value or {}).get("category"),
                                            "summary": (updated_memory.value or {}).get("summary"),
                                            "importance": (updated_memory.value or {}).get("importance"),
                                            "created_at": updated_memory.created_at,
                                            "updated_at": updated_memory.updated_at,
                                            "value": updated_memory.value,
                                        },
                                    }
                                )
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
                            await queue.put(
                                {
                                    "event": "memory.updated",
                                    "data": {
                                        "id": updated_memory.key,
                                        "type": mem_type,
                                        "category": (updated_memory.value or {}).get("category"),
                                        "summary": (updated_memory.value or {}).get("summary"),
                                        "importance": (updated_memory.value or {}).get("importance"),
                                        "created_at": updated_memory.created_at,
                                        "updated_at": updated_memory.updated_at,
                                        "value": updated_memory.value,
                                    },
                                }
                            )
                    break
        if not did_update:
            if int(candidate_value.get("importance") or 1) < SEMANTIC_MIN_IMPORTANCE:
                logger.info("memory.skip: below_min_importance=%s", SEMANTIC_MIN_IMPORTANCE)
            else:
                t0p = time.perf_counter()
                ns0_present = bool(namespace and namespace[0])
                ns1 = namespace[1] if len(namespace) > 1 else ""
                logger.info("memory.store.put.start ns0_set=%s ns1=%s mode=create", ns0_present, ns1)
                store.put(namespace, candidate_value["id"], candidate_value, index=["summary"])  # async context
                t1p = time.perf_counter()
                logger.info("memory.store.put.done ms=%d", int((t1p - t0p) * 1000))
                logger.info("memory.create: id=%s type=%s category=%s", candidate_value["id"], "semantic", category)

                asyncio.create_task(_profile_sync_from_memory(user_id, thread_id, candidate_value))
                if queue:
                    with contextlib.suppress(Exception):
                        await queue.put(
                            {
                                "event": "memory.created",
                                "data": {
                                    "id": candidate_value["id"],
                                    "type": mem_type,
                                    "category": category,
                                    "summary": candidate_value.get("summary"),
                                    "importance": candidate_value.get("importance"),
                                    "created_at": candidate_value.get("created_at"),
                                    "updated_at": candidate_value.get("updated_at"),
                                    "value": candidate_value,
                                },
                            }
                        )
    except Exception:
        logger.exception("memory_hotpath.error: id=%s", candidate_value.get("id"))
        if thread_id:
            try:
                queue = get_sse_queue(thread_id)
                await queue.put({"event": "memory.error", "data": {"id": candidate_value.get("id")}})
            except Exception:
                pass


def _same_fact_classify(existing_summary: str, candidate_summary: str, category: str) -> bool:
    from app.services.llm.prompt_loader import prompt_loader
    prompt = prompt_loader.load("memory_same_fact_classifier",
                               category=category[:64],
                               existing_summary=existing_summary[:500],
                               candidate_summary=candidate_summary[:500])
    bedrock = get_bedrock_runtime_client()
    try:
        t0 = time.perf_counter()
        logger.info("memory.llm.samefact.start model=%s", MODEL_ID)
        body_payload = {
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"temperature": 0.0, "topP": 0.1, "maxTokens": 128, "stopSequences": []},
        }
        res = bedrock.invoke_model(modelId=MODEL_ID, body=json.dumps(body_payload))
        t1 = time.perf_counter()
        logger.info("memory.llm.samefact.done ms=%d", int((t1 - t0) * 1000))
        body = res.get("body")
        txt = body.read().decode("utf-8") if hasattr(body, "read") else str(body)
        data = json.loads(txt)
        out_text = ""
        try:
            contents = data.get("output", {}).get("message", {}).get("content", "")
            if isinstance(contents, list):
                for part in contents:
                    if isinstance(part, dict) and part.get("text"):
                        out_text += part.get("text", "")
            elif isinstance(contents, str):
                out_text = contents
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
                out = json.loads(out_text[i : j + 1])
            else:
                return False
        return bool(out.get("same_fact") is True)
    except Exception:
        logger.exception("same_fact.error")
        return False


def _compose_summaries(existing_summary: str, candidate_summary: str, category: str) -> str:
    from app.services.llm.prompt_loader import prompt_loader
    prompt = prompt_loader.load("memory_compose_summaries",
                               category=category[:64],
                               existing_summary=existing_summary[:500],
                               candidate_summary=candidate_summary[:500])
    bedrock = get_bedrock_runtime_client()
    try:
        t0 = time.perf_counter()
        logger.info("memory.llm.compose.start model=%s", MODEL_ID)
        body_payload = {
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"temperature": 0.2, "topP": 0.5, "maxTokens": 160, "stopSequences": []},
        }
        res = bedrock.invoke_model(modelId=MODEL_ID, body=json.dumps(body_payload))
        t1 = time.perf_counter()
        logger.info("memory.llm.compose.done ms=%d", int((t1 - t0) * 1000))
        body = res.get("body")
        txt = body.read().decode("utf-8") if hasattr(body, "read") else str(body)
        data = json.loads(txt)
        out_text = ""
        try:
            contents = data.get("output", {}).get("message", {}).get("content", "")
            if isinstance(contents, list):
                for part in contents:
                    if isinstance(part, dict) and part.get("text"):
                        out_text += part.get("text", "")
            elif isinstance(contents, str):
                out_text = contents
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
    t = t.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    return t


def _derive_nudge_metadata(category: str, summary: str, importance: int) -> dict[str, Any]:
    from datetime import datetime, timezone

    metadata = {}
    datetime.now(tz=timezone.utc)

    topic_key = "general"
    summary_lower = summary.lower()

    if category == "Finance":
        if any(word in summary_lower for word in ["subscription", "recurring", "monthly", "annual"]):
            topic_key = "subscription"
        elif any(word in summary_lower for word in ["spending", "expense", "purchase"]):
            topic_key = "spending_pattern"
        elif any(word in summary_lower for word in ["bill", "payment", "due"]):
            topic_key = "bill"
        else:
            topic_key = "finance_general"
    elif category == "Budget":
        if any(word in summary_lower for word in ["budget", "limit", "allocation"]):
            topic_key = "budget_status"
        else:
            topic_key = "budget_general"
    elif category == "Goals":
        if any(word in summary_lower for word in ["goal", "target", "achieve", "save", "saving"]):
            topic_key = "goal_active"
        elif any(word in summary_lower for word in ["milestone", "progress", "reached"]):
            topic_key = "achievement"
        else:
            topic_key = "goals_general"
    elif category == "Personal":
        topic_key = "personal_info"
    elif category == "Education":
        topic_key = "education_interest"

    metadata["topic_key"] = topic_key

    if importance >= 4:
        metadata["importance_bin"] = "high"
    elif importance >= 2:
        metadata["importance_bin"] = "med"
    else:
        metadata["importance_bin"] = "low"

    return metadata


# Combined regex pattern for time sanitization (single pass)
_TIME_SANITIZATION_PATTERN = re.compile(
    r"\b(today|yesterday|tomorrow|this\s+(morning|afternoon|evening|tonight)|"
    r"(last|next)\s+(week|month|year)|recently|soon|earlier|later|now)\b|"
    r"\bon\s+\d{4}-\d{2}-\d{2}\b|\bthis\s+year\b",
    re.IGNORECASE,
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
        thread_id = get_config_value(config, "thread_id")
        user_id = get_config_value(config, "user_id")
        if user_id and recent_user_texts:
            synthetic_value = {
                "category": "Personal",
                "summary": _sanitize_semantic_time_phrases(recent_user_texts[-1])[:280],
            }
            asyncio.create_task(_profile_sync_from_memory(user_id, thread_id, synthetic_value))

        ctx = get_config_value(config, "user_context") or {}
        prof = _build_profile_line(ctx) if isinstance(ctx, dict) else None
        return {"messages": [AIMessage(content=prof)]} if prof else {}

    thread_id = get_config_value(config, "thread_id")
    user_id = get_config_value(config, "user_id")
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
        ctx = get_config_value(config, "user_context") or {}
        prof = _build_profile_line(ctx) if isinstance(ctx, dict) else None
        return {"messages": [HumanMessage(content=prof)]} if prof else {}

    candidate_id = uuid4().hex
    now = _utc_now_iso()
    importance = int(trigger.get("importance") or 1)

    nudge_metadata = _derive_nudge_metadata(category, summary, importance)

    candidate_value: dict[str, Any] = {
        "id": candidate_id,
        "user_id": user_id,
        "type": "semantic",
        "summary": summary,
        "category": category,
        "source": "chat",
        "importance": importance,
        "created_at": now,
        "last_used_at": None,
        **nudge_metadata,
    }

    logger.info(
        "memory_hotpath.candidate: id=%s type=%s category=%s topic_key=%s importance_bin=%s summary_preview=%s",
        candidate_id,
        mem_type,
        category,
        nudge_metadata.get("topic_key"),
        nudge_metadata.get("importance_bin"),
        (summary[:80] + ("…" if len(summary) > 80 else "")),
    )

    if int(candidate_value.get("importance") or 1) >= SEMANTIC_MIN_IMPORTANCE and thread_id:
        try:
            queue = get_sse_queue(thread_id)
            await queue.put(
                {
                    "event": "memory.created",
                    "data": {"id": candidate_id, "type": mem_type, "category": category, "summary": summary},
                }
            )
        except Exception:
            pass

    asyncio.create_task(
        _write_semantic_memory(
            user_id=user_id,
            thread_id=thread_id,
            category=category,
            summary=summary,
            candidate_value=candidate_value,
            mem_type=mem_type,
            candidate_id=candidate_id,
        )
    )
    ctx = get_config_value(config, "user_context") or {}
    prof = _build_profile_line(ctx) if isinstance(ctx, dict) else None
    return {"messages": [AIMessage(content=prof)]} if prof else {}
