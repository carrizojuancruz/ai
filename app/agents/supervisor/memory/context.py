from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone, tzinfo
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_store
from langgraph.graph import MessagesState

from .utils import _parse_iso, _parse_weights

logger = logging.getLogger(__name__)

# Environment variables
CONTEXT_TOPK = int(os.getenv("MEMORY_CONTEXT_TOPK", "24"))
CONTEXT_TOPN = int(os.getenv("MEMORY_CONTEXT_TOPN", "5"))
RERANK_WEIGHTS_RAW = os.getenv("MEMORY_RERANK_WEIGHTS", "sim=0.55,imp=0.20,recency=0.15,pinned=0.10")


def _extract_user_text(messages: list[Any]) -> str | None:
    user_text: str | None = None
    for m in reversed(messages):
        role = getattr(m, "role", getattr(m, "type", None))
        if role in ("user", "human"):
            candidate = getattr(m, "content", None)
            if isinstance(candidate, str) and (
                candidate.startswith("CONTEXT_PROFILE:") or
                candidate.startswith("Relevant context for tailoring this turn:")
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
        return weights["sim"] * sim + weights["imp"] * (imp / 5.0) + weights["recency"] * recency + weights["pinned"] * pinned

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


def _items_to_bullets(epi_items: list[Any], sem_items: list[Any], topn: int) -> list[str]:
    bullets: list[str] = []
    for it in epi_items[:2]:
        val = getattr(it, "value", {}) or {}
        txt = val.get("summary")
        if txt:
            bullets.append(f"[{val.get('category')}] {txt}")
    for it in sem_items[: max(1, topn)]:
        val = getattr(it, "value", {}) or {}
        txt = val.get("summary")
        if txt:
            bullets.append(f"[{val.get('category')}] {txt}")
    return bullets


def _resolve_user_tz_from_config(config: RunnableConfig) -> tzinfo:
    ctx = config.get("configurable", {}).get("user_context") or {}
    tzname = ((ctx.get("locale_info", {}) or {}).get("time_zone") or "UTC") if isinstance(ctx, dict) else "UTC"
    try:
        import zoneinfo
        return zoneinfo.ZoneInfo(tzname)
    except Exception:
        return timezone.utc


def _build_context_response(bullets: list[str], config: RunnableConfig) -> dict:
    user_tz: tzinfo = _resolve_user_tz_from_config(config)
    now_local = datetime.now(tz=user_tz)
    date_bullet = f"Now: {now_local.strftime('%Y-%m-%d %H:%M %Z')}"
    all_bullets = ([date_bullet] if date_bullet else []) + bullets
    context_str = "Relevant context for tailoring this turn:\n- " + "\n- ".join(all_bullets)
    return {"messages": [HumanMessage(content=context_str)]}


async def memory_context(state: MessagesState, config: RunnableConfig) -> dict:
    messages = state["messages"]
    user_text = _extract_user_text(messages)
    user_id = config.get("configurable", {}).get("user_id")
    if not user_id:
        return {}

    w = _parse_weights(RERANK_WEIGHTS_RAW)
    try:
        store = get_store()
        query_text = (user_text or "").strip() or "personal profile"
        logger.info("memory_context.query: user_id=%s query=%s", user_id, (query_text[:200]))
        sem = store.search((user_id, "semantic"), query=query_text, filter=None, limit=CONTEXT_TOPK)
        epi = store.search((user_id, "episodic"), query=query_text, filter=None, limit=max(3, CONTEXT_TOPK // 2))
        logger.info("memory_context.results: sem=%d epi=%d", len(sem or []), len(epi or []))
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
        bullets = _items_to_bullets(epi_sorted, merged_sem, CONTEXT_TOPN)
        logger.info("memory_context.bullets.count: %d", len(bullets))
    except Exception:
        pass

    if not locals().get("bullets"):
        return {}
    return _build_context_response(bullets, config)


