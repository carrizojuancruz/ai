from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Any
from uuid import uuid4

import boto3
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_store
from langgraph.graph import MessagesState

from app.core.app_state import get_sse_queue
from app.repositories.session_store import get_session_store

from .utils import _parse_iso, _utc_now_iso

logger = logging.getLogger(__name__)


# Environment variables
EPISODIC_COOLDOWN_TURNS = int(os.getenv("EPISODIC_COOLDOWN_TURNS", "3"))
EPISODIC_COOLDOWN_MINUTES = int(os.getenv("EPISODIC_COOLDOWN_MINUTES", "10"))
EPISODIC_MAX_PER_DAY = int(os.getenv("EPISODIC_MAX_PER_DAY", "5"))
EPISODIC_WINDOW_N = int(os.getenv("EPISODIC_WINDOW_N", "10"))
EPISODIC_MERGE_WINDOW_HOURS = int(os.getenv("EPISODIC_MERGE_WINDOW_HOURS", "48"))
EPISODIC_NOVELTY_MIN = float(os.getenv("EPISODIC_NOVELTY_MIN", "0.90"))
MEMORY_TINY_LLM_MODEL_ID = os.getenv("MEMORY_TINY_LLM_MODEL_ID", "amazon.nova-micro-v1:0")
AWS_REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))


def _resolve_user_tz_from_config(config: RunnableConfig) -> tzinfo:
    """Return user's tzinfo from config; fallback to UTC when unavailable/invalid."""
    ctx = config.get("configurable", {}).get("user_context") or {}
    tzname = ((ctx.get("locale_info", {}) or {}).get("time_zone") or "UTC") if isinstance(ctx, dict) else "UTC"
    try:
        import zoneinfo
        return zoneinfo.ZoneInfo(tzname)
    except Exception:
        return timezone.utc


async def _load_session_store_and_ctrl(thread_id: str | None) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    """Load session store, current session payload and episodic control structure."""
    session_store = get_session_store()
    sess = await session_store.get_session(thread_id) or {}
    ctrl = dict(sess.get("episodic_control") or {})
    return session_store, sess, ctrl


def _update_ctrl_for_new_turn(ctrl: dict[str, Any], date_iso: str) -> dict[str, Any]:
    """Roll daily counters and increment turns_since_last for a new user turn."""
    if ctrl.get("day_iso") != date_iso:
        ctrl["day_iso"] = date_iso
        ctrl["count_today"] = 0
    ctrl["turns_since_last"] = int(ctrl.get("turns_since_last") or 0) + 1
    return ctrl


def _should_skip_capture(
    ctrl: dict[str, Any],
    now_utc: datetime,
    *,
    minutes_cooldown: int,
    turns_cooldown: int,
    max_per_day: int,
) -> bool:
    """Decide whether to skip capture based on cooldowns and daily caps."""
    last_at_iso = ctrl.get("last_at_iso")
    last_dt = _parse_iso(last_at_iso) if isinstance(last_at_iso, str) else None
    recent_minutes_ok = not (last_dt and (now_utc - last_dt).total_seconds() < minutes_cooldown * 60)
    return (
        (ctrl.get("count_today", 0) >= max_per_day)
        or (int(ctrl.get("turns_since_last") or 0) < turns_cooldown)
        or (not recent_minutes_ok)
    )


def _collect_recent_messages(state: MessagesState, max_messages: int) -> list[tuple[str, str]]:
    """Collect the latest N user/assistant messages in chronological order."""
    msgs: list[tuple[str, str]] = []
    for m in reversed(state["messages"]):
        role = getattr(m, "role", getattr(m, "type", None))
        if role not in ("user", "human", "assistant", "ai"):
            continue
        content = getattr(m, "content", None)
        if isinstance(content, str) and content.strip():
            msgs.append((str(role), content.strip()))
        if len(msgs) >= max_messages:
            break
    return list(reversed(msgs))


def _summarize_with_bedrock(msgs: list[tuple[str, str]]) -> tuple[str, str, int]:
    """Call Bedrock to generate a JSON summary; return (summary, category, importance)."""
    model_id = MEMORY_TINY_LLM_MODEL_ID
    region = AWS_REGION
    bedrock = boto3.client("bedrock-runtime", region_name=region)
    convo = "\n".join([f"{r.title()}: {t}" for r, t in msgs])[:2000]
    prompt = (
        "Summarize the interaction in 1–2 sentences focusing on what was discussed/decided/done. "
        "Exclude stable facts already known unless updated. Output strict JSON: "
        '{"summary": string, "category": string, "importance": 1..5}. '
        "Use concise neutral phrasing.\n\nConversation:\n" + convo + "\nJSON:"
    )
    body_payload = {
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"temperature": 0.0, "topP": 0.1, "maxTokens": 128, "stopSequences": []},
    }
    res = bedrock.invoke_model(modelId=model_id, body=json.dumps(body_payload))
    body = res.get("body")
    raw = body.read().decode("utf-8") if hasattr(body, "read") else str(body)
    data = json.loads(raw)
    out_text = ""
    try:
        contents = data.get("output", {}).get("message", {}).get("content", [])
        for part in contents:
            if isinstance(part, dict) and part.get("text"):
                out_text += part.get("text", "")
    except Exception:
        out_text = data.get("outputText") or data.get("generation") or ""
    parsed: dict[str, Any] = {}
    if out_text:
        try:
            parsed = json.loads(out_text)
        except Exception:
            i, j = out_text.find("{"), out_text.rfind("}")
            parsed = json.loads(out_text[i:j+1]) if i != -1 and j != -1 and j > i else {}
    epi_summary = str(parsed.get("summary") or "").strip()[:280]
    epi_category = str(parsed.get("category") or "Conversation_Summary").strip() or "Conversation_Summary"
    epi_importance = int(parsed.get("importance") or 1)
    return epi_summary, epi_category, epi_importance


def _build_human_summary(epi_summary: str, date_iso: str, now_local: datetime) -> str:
    """Format a human-readable episodic summary with date/week metadata."""
    week = int(now_local.strftime("%V"))
    year = now_local.year
    return f"On {date_iso} (W{week}, {year}) {epi_summary}"


def _get_neighbors(store: Any, namespace: tuple[str, ...], query: str, *, limit: int = 5) -> list[Any]:
    """Query nearest episodic neighbors with safe fallback to empty list."""
    try:
        return store.search(namespace, query=query, filter=None, limit=limit)
    except Exception:
        return []


def _should_merge_neighbor(best: Any, now_utc: datetime, novelty_min: float, merge_window_hours: int) -> bool:
    """Determine if an existing neighbor should be merged based on recency and similarity."""
    score_val = float(getattr(best, "score", 0.0) or 0.0)
    ts = _parse_iso(getattr(best, "updated_at", "")) or _parse_iso(getattr(best, "created_at", ""))
    within_window = True
    if ts:
        within_window = (now_utc - ts) <= timedelta(hours=merge_window_hours)
    return score_val >= novelty_min and within_window


async def _merge_existing_if_applicable(
    store: Any,
    namespace: tuple[str, ...],
    best: Any,
    human_summary: str,
    thread_id: str | None,
    session_store: Any,
    sess: dict[str, Any],
    ctrl: dict[str, Any],
    now_utc: datetime,
) -> bool:
    """Merge into an existing episodic item if present; emit events and persist control."""
    existing = store.get(namespace, getattr(best, "key", ""))
    if existing:
        merged = dict(existing.value)
        merged["last_accessed"] = _utc_now_iso()
        if human_summary and len(human_summary) > len(merged.get("summary", "")):
            merged["summary"] = human_summary
        store.put(namespace, existing.key, merged, index=["summary"])  # re-embed
        logger.info("episodic.merge: key=%s score=%.3f", existing.key, float(getattr(best, "score", 0.0) or 0.0))
        if thread_id:
            try:
                queue = get_sse_queue(thread_id)
                await queue.put({"event": "episodic.updated", "data": {"id": existing.key}})
            except Exception:
                pass
        ctrl = _reset_ctrl_after_capture(ctrl, now_utc)
        sess["episodic_control"] = ctrl
        await session_store.set_session(thread_id, sess)
        return True
    return False


def _create_episodic_value(
    *,
    user_id: str,
    candidate_id: str,
    human_summary: str,
    category: str,
    importance: int,
    now_iso: str,
) -> dict[str, Any]:
    """Build the episodic value payload to store, given inputs and timestamps."""
    return {
        "id": candidate_id,
        "user_id": user_id,
        "type": "episodic",
        "summary": human_summary,
        "category": category,
        "tags": [],
        "source": "chat",
        "importance": importance,
        "pinned": False,
        "created_at": now_iso,
        "last_accessed": now_iso,
    }


async def _emit_created_event(thread_id: str | None, candidate_id: str) -> None:
    """Emit SSE event for a newly created episodic item if a thread is available."""
    if not thread_id:
        return
    try:
        queue = get_sse_queue(thread_id)
        await queue.put({"event": "episodic.created", "data": {"id": candidate_id}})
    except Exception:
        pass


def _reset_ctrl_after_capture(ctrl: dict[str, Any], now_utc: datetime) -> dict[str, Any]:
    """Reset episodic control counters after a successful capture/merge."""
    ctrl["turns_since_last"] = 0
    ctrl["last_at_iso"] = now_utc.isoformat()
    ctrl["count_today"] = int(ctrl.get("count_today") or 0) + 1
    return ctrl


async def _persist_session_ctrl(session_store: Any, thread_id: str | None, sess: dict[str, Any], ctrl: dict[str, Any]) -> None:
    """Persist episodic control state back into the session store."""
    sess["episodic_control"] = ctrl
    await session_store.set_session(thread_id, sess)


async def episodic_capture(state: MessagesState, config: RunnableConfig) -> dict:
    """Orchestrate episodic memory capture: cooldown checks, summarization, dedupe/merge, persistence, and SSE notifications.

    Returns empty dict as a node output.
    """
    try:
        user_id = config.get("configurable", {}).get("user_id")
        thread_id = config.get("configurable", {}).get("thread_id")
        if not user_id:
            return {}

        turns_cooldown = EPISODIC_COOLDOWN_TURNS
        minutes_cooldown = EPISODIC_COOLDOWN_MINUTES
        max_per_day = EPISODIC_MAX_PER_DAY

        user_tz = _resolve_user_tz_from_config(config)
        now_local = datetime.now(tz=user_tz)
        date_iso = now_local.date().isoformat()
        now_utc = datetime.now(tz=timezone.utc)

        session_store, sess, ctrl = await _load_session_store_and_ctrl(thread_id)
        ctrl = _update_ctrl_for_new_turn(ctrl, date_iso)
        if _should_skip_capture(
            ctrl,
            now_utc,
            minutes_cooldown=minutes_cooldown,
            turns_cooldown=turns_cooldown,
            max_per_day=max_per_day,
        ):
            await _persist_session_ctrl(session_store, thread_id, sess, ctrl)
            logger.info("episodic.decide: skip reason=cooldown_or_daily_cap")
            return {}

        N = EPISODIC_WINDOW_N
        msgs = _collect_recent_messages(state, N)
        if not msgs:
            return {}

        try:
            epi_summary, epi_category, epi_importance = _summarize_with_bedrock(msgs)
        except Exception:
            logger.exception("episodic.summarize.error")
            return {}
        if not epi_summary:
            return {}

        human_summary = _build_human_summary(epi_summary, date_iso, now_local)

        store = get_store()
        namespace = (user_id, "episodic")
        merge_window_hours = EPISODIC_MERGE_WINDOW_HOURS
        novelty_min = EPISODIC_NOVELTY_MIN

        neighbors = _get_neighbors(store, namespace, human_summary, limit=5)
        best = neighbors[0] if neighbors else None
        if (
            best
            and isinstance(getattr(best, "score", None), (int, float))
            and _should_merge_neighbor(best, now_utc, novelty_min, merge_window_hours)
        ):
            merged = await _merge_existing_if_applicable(
                store,
                namespace,
                best,
                human_summary,
                thread_id,
                session_store,
                sess,
                ctrl,
                now_utc,
            )
            if merged:
                return {}

        candidate_id = uuid4().hex
        now_iso = _utc_now_iso()
        value = _create_episodic_value(
            user_id=user_id,
            candidate_id=candidate_id,
            human_summary=human_summary,
            category=epi_category,
            importance=epi_importance,
            now_iso=now_iso,
        )
        store.put(namespace, candidate_id, value, index=["summary"])  # async context
        logger.info("episodic.create: id=%s", candidate_id)
        await _emit_created_event(thread_id, candidate_id)
        ctrl = _reset_ctrl_after_capture(ctrl, now_utc)
        await _persist_session_ctrl(session_store, thread_id, sess, ctrl)
        return {}
    except Exception:
        logger.exception("episodic_capture.error")
        return {}


