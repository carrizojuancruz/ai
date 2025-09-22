from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone, tzinfo
from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_store
from langgraph.graph import MessagesState

from app.core.config import config
from app.utils.tools import get_config_value

from .utils import _parse_iso, _parse_weights

logger = logging.getLogger(__name__)

# Config variables
CONTEXT_TOPK = config.MEMORY_CONTEXT_TOPK
CONTEXT_TOPN = config.MEMORY_CONTEXT_TOPN
RERANK_WEIGHTS_RAW = config.MEMORY_RERANK_WEIGHTS
PROCEDURAL_TOPK = config.MEMORY_PROCEDURAL_TOPK
PROCEDURAL_MIN_SCORE = float(config.MEMORY_PROCEDURAL_MIN_SCORE)


def _extract_user_text(messages: list[Any]) -> str | None:
    user_text: str | None = None
    for m in reversed(messages):
        role = getattr(m, "role", getattr(m, "type", None))
        if role in ("user", "human"):
            candidate = getattr(m, "content", None)
            if isinstance(candidate, str) and (
                candidate.startswith("CONTEXT_PROFILE:")
                or candidate.startswith("Relevant context for tailoring this turn:")
            ):
                continue
            user_text = candidate
            break
    return user_text


def _score_factory(weights: dict[str, float]):
    def _score(item: Any) -> float:
        sim = float(getattr(item, "score", 0.0) or 0.0)
        val = getattr(item, "value", {}) or {}
        imp = float(val.get("importance") or 0)
        pinned = 1.0 if bool(val.get("pinned")) else 0.0
        ts = _parse_iso(getattr(item, "updated_at", ""))
        recency = 0.0
        if ts:
            age_days = max(0.0, (datetime.now(tz=timezone.utc) - ts).total_seconds() / 86400.0)
            recency = 1.0 / (1.0 + age_days)
        return (
            weights["sim"] * sim
            + weights["imp"] * (imp / 5.0)
            + weights["recency"] * recency
            + weights["pinned"] * pinned
        )

    return _score


def _merge_semantic_items(sem_results: list[Any], topn: int, score_fn) -> list[Any]:
    raw_sorted = sorted(sem_results, key=lambda it: float(getattr(it, "score", 0.0) or 0.0), reverse=True)
    pre_raw = raw_sorted[:2]
    reranked_full = sorted(sem_results, key=score_fn, reverse=True)
    merged_sem: list[Any] = []
    seen_keys: set[str | None] = set()
    for it in pre_raw:
        k = getattr(it, "key", None)
        if k not in seen_keys:
            merged_sem.append(it)
            seen_keys.add(k)
    for it in reranked_full:
        if len(merged_sem) >= max(1, topn):
            break
        k = getattr(it, "key", None)
        if k not in seen_keys:
            merged_sem.append(it)
            seen_keys.add(k)
    return merged_sem


def _select_episodic_items(epi_results: list[Any], topn: int, score_fn) -> list[Any]:
    limit = max(1, topn // 2) if topn else 1
    return sorted(epi_results, key=score_fn, reverse=True)[:limit]


def _items_to_bullets(epi_items: list[Any], sem_items: list[Any], topn: int, user_tz: tzinfo) -> list[str]:
    bullets: list[str] = []

    def _format_suffix(item: Any, val: dict[str, Any]) -> str:
        ts_updated = getattr(item, "updated_at", None)
        ts_created = getattr(item, "created_at", None)
        ts_value = val.get("last_accessed") or val.get("created_at")
        ts_str = ts_updated or ts_created or ts_value
        if not isinstance(ts_str, str):
            return ""
        dt = _parse_iso(ts_str)
        if dt is None:
            return ""
        try:
            local = dt.astimezone(user_tz)
        except Exception:
            local = dt
        label = "Updated on" if ts_updated else "Created on"
        return f" — {label} {local.strftime('%Y-%m-%d')}"

    # Episodic bullets: keep summary text; append created/updated date for clarity
    for it in epi_items[:2]:
        val = getattr(it, "value", {}) or {}
        txt = val.get("summary")
        if not txt:
            continue
        bullets.append(f"[{val.get('category')}] {txt}{_format_suffix(it, val)}")

    # Semantic bullets: append created/updated date (recency signal)
    for it in sem_items[: max(1, topn)]:
        val = getattr(it, "value", {}) or {}
        txt = val.get("summary")
        if not txt:
            continue
        bullets.append(f"[{val.get('category')}] {txt}{_format_suffix(it, val)}")
    return bullets


def _resolve_user_tz_from_config(config: RunnableConfig) -> tzinfo:
    ctx = get_config_value(config, "user_context") or {}
    tzname = ((ctx.get("locale_info", {}) or {}).get("time_zone") or "UTC") if isinstance(ctx, dict) else "UTC"
    try:
        import zoneinfo

        return zoneinfo.ZoneInfo(tzname)
    except Exception:
        return timezone.utc


async def _timed_search(store: Any, namespace: tuple[str, str], *, query: str, limit: int, label: str) -> list[Any]:
    t0 = time.perf_counter()
    results = await asyncio.to_thread(store.search, namespace, query=query, filter=None, limit=limit)
    t1 = time.perf_counter()
    logger.info("memory_context.%s.done ms=%d results=%d", label, int((t1 - t0) * 1000), len(results or []))
    return results


def _extract_routing_examples(proc: list[Any] | None) -> list[str]:
    """Extract routing examples from procedural memories with proper error handling.

    Args:
        proc: List of procedural memory items

    Returns:
        List of formatted routing example strings

    """
    if not proc:
        return []

    routing_examples: list[str] = []

    for it in proc[:int(PROCEDURAL_TOPK)]:
        try:
            score_val = _safe_extract_score(it)
            if score_val < PROCEDURAL_MIN_SCORE:
                continue

            summary_text = _safe_extract_summary(it)
            if not summary_text:
                continue

            if len(summary_text) > 240:
                summary_text = summary_text[:237] + "..."

            routing_examples.append(f"Example: {summary_text}")

        except (AttributeError, TypeError) as e:
            logger.debug("Skipping invalid procedural memory item: %s", e)
            continue

    return routing_examples


def _safe_extract_score(item: Any) -> float:
    """Safely extract score from memory item with specific exception handling."""
    try:
        raw_score = getattr(item, "score", 0.0) or 0.0
        return float(raw_score)
    except (ValueError, TypeError) as e:
        logger.debug("Failed to convert score to float: %s", e)
        return 0.0


def _safe_extract_summary(item: Any) -> str:
    """Safely extract summary text from memory item."""
    try:
        val = getattr(item, "value", {}) or {}
        summary_text = str(val.get("summary") or "").strip()
        return summary_text
    except (AttributeError, TypeError) as e:
        logger.debug("Failed to extract summary: %s", e)
        return ""


def _build_context_response(bullets: list[str], config: RunnableConfig, routing_examples: list[str] | None = None) -> dict:
    user_tz: tzinfo = _resolve_user_tz_from_config(config)
    now_local = datetime.now(tz=user_tz)
    date_bullet = f"Now: {now_local.strftime('%Y-%m-%d %H:%M %Z')}"
    all_bullets = ([date_bullet] if date_bullet else []) + bullets
    if routing_examples:
        all_bullets.extend(["", "Few-shot Routing examples:\n"] + routing_examples)
    context_str = "Relevant context for tailoring this turn:\n- " + "\n- ".join(all_bullets)
    return {"messages": [AIMessage(content=context_str)]}


async def memory_context(state: MessagesState, config: RunnableConfig) -> dict:
    messages = state["messages"]
    user_text = _extract_user_text(messages)
    user_id = get_config_value(config, "user_id")
    if not user_id:
        return {}

    w = _parse_weights(RERANK_WEIGHTS_RAW)
    try:
        store = get_store()
        query_text = (user_text or "").strip() or "personal profile"
        logger.info("memory_context.query: user_id=%s query=%s", user_id, (query_text[:200]))

        t0s = time.perf_counter()
        sem_task = _timed_search(
            store, (user_id, "semantic"), query=query_text, limit=int(CONTEXT_TOPK), label="semantic"
        )
        epi_task = _timed_search(
            store, (user_id, "episodic"), query=query_text, limit=int(max(3, CONTEXT_TOPK // 2)), label="episodic"
        )
        proc_task = _timed_search(
            store,
            ("system", "supervisor_procedural"),
            query=query_text,
            limit=int(PROCEDURAL_TOPK),
            label="procedural",
        )
        sem, epi, proc = await asyncio.gather(sem_task, epi_task, proc_task)
        t1s = time.perf_counter()
        logger.info("memory_context.search.total ms=%d", int((t1s - t0s) * 1000))
        logger.info("memory_context.results: sem=%d epi=%d proc=%d", len(sem or []), len(epi or []), len(proc or []))
        score = _score_factory(w)
        merged_sem = _merge_semantic_items(sem, CONTEXT_TOPN, score)
        try:
            sem_preview = [
                {
                    "key": getattr(it, "key", None),
                    "score": float(getattr(it, "score", 0.0) or 0.0),
                    "category": (getattr(it, "value", {}) or {}).get("category"),
                    "summary_preview": ((getattr(it, "value", {}) or {}).get("summary") or "")[:80],
                }
                for it in merged_sem[:CONTEXT_TOPN]
            ]
            logger.info("memory_context.sem.top: %s", json.dumps(sem_preview))
        except Exception as e:
            logger.debug("Failed to log semantic preview: %s", e)

        epi_sorted = _select_episodic_items(epi, CONTEXT_TOPN, score)
        user_tz = _resolve_user_tz_from_config(config)
        bullets = _items_to_bullets(epi_sorted, merged_sem, CONTEXT_TOPN, user_tz)
        logger.info("memory_context.bullets.count: %d", len(bullets))

        routing_examples = _extract_routing_examples(proc)
    except Exception:
        pass

    if not locals().get("bullets"):
        return {}
    return _build_context_response(bullets, config, routing_examples)
