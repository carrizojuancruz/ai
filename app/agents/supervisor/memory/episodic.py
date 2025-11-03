from __future__ import annotations

import contextlib
import json
import logging
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Any
from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.config import get_store
from langgraph.graph import MessagesState

from app.core.app_state import get_bedrock_runtime_client, get_sse_queue
from app.core.config import config as app_config
from app.repositories.session_store import get_session_store
from app.services.memory_service import memory_service
from app.utils.tools import get_config_value

from .utils import _parse_iso, _utc_now_iso

logger = logging.getLogger(__name__)


# Config variables
EPISODIC_COOLDOWN_TURNS = app_config.EPISODIC_COOLDOWN_TURNS
EPISODIC_COOLDOWN_MINUTES = app_config.EPISODIC_COOLDOWN_MINUTES
EPISODIC_MAX_PER_DAY = app_config.EPISODIC_MAX_PER_DAY
EPISODIC_WINDOW_N = app_config.EPISODIC_WINDOW_N
EPISODIC_MERGE_WINDOW_HOURS = app_config.EPISODIC_MERGE_WINDOW_HOURS
EPISODIC_NOVELTY_MIN = app_config.EPISODIC_NOVELTY_MIN
MEMORY_TINY_LLM_MODEL_ID = app_config.MEMORY_TINY_LLM_MODEL_ID
AWS_REGION = app_config.get_aws_region()


def _resolve_user_tz_from_config(config: RunnableConfig) -> tzinfo:
    """Return user's tzinfo from config; fallback to UTC when unavailable/invalid."""
    ctx = get_config_value(config, "user_context") or {}
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
    bedrock = get_bedrock_runtime_client()
    from app.services.llm.prompt_loader import prompt_loader
    convo = "\n".join([f"{r.title()}: {t}" for r, t in msgs])[:2000]
    prompt = prompt_loader.load("episodic_memory_summarizer",
                               conversation=convo)
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
        contents = data.get("output", {}).get("message", {}).get("content", "")
        if isinstance(contents, list):
            for part in contents:
                if isinstance(part, dict) and part.get("text"):
                    out_text += part.get("text", "")
        elif isinstance(contents, str):
            out_text = contents
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
            with contextlib.suppress(Exception):
                await _emit_memory_event(thread_id, existing.key, merged, is_created=False)
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
        "last_accessed": None,
    }


async def _emit_memory_event(thread_id: str | None, memory_id: str, value: dict[str, Any], is_created: bool = True) -> None:
    """Emit SSE event for episodic memory creation or update."""
    if not thread_id:
        return
    try:
        queue = get_sse_queue(thread_id)
        event_type = "episodic.created" if is_created else "episodic.updated"
        await queue.put({"event": event_type, "data": {
            "id": memory_id,
            "type": "episodic",
            "category": value.get("category"),
            "summary": value.get("summary"),
            "importance": value.get("importance"),
            "created_at": value.get("created_at"),
            "updated_at": value.get("last_accessed"),
            "value": value
        }})
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
        user_id = get_config_value(config, "user_id")
        thread_id = get_config_value(config, "thread_id")
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

        memory_service.create_memory(
            user_id=user_id,
            memory_type="episodic",
            key=candidate_id,
            value=value,
            index=["summary"]
        )

        logger.info("episodic.create: id=%s", candidate_id)
        await _emit_memory_event(thread_id, candidate_id, value, is_created=True)
        ctrl = _reset_ctrl_after_capture(ctrl, now_utc)
        await _persist_session_ctrl(session_store, thread_id, sess, ctrl)
        return {}
    except Exception:
        logger.exception("episodic_capture.error")
        return {}


