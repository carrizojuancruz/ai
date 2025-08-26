from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any
from uuid import uuid4

import boto3
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_store
from langgraph.graph import MessagesState

from app.core.app_state import get_sse_queue
from app.repositories.session_store import get_session_store
from .utils import _utc_now_iso, _parse_iso

logger = logging.getLogger(__name__)


async def episodic_capture(state: MessagesState, config: RunnableConfig) -> dict:
    try:
        user_id = config.get("configurable", {}).get("user_id")
        thread_id = config.get("configurable", {}).get("thread_id")
        if not user_id:
            return {}

        turns_cooldown = int(os.getenv("EPISODIC_COOLDOWN_TURNS", "3"))
        minutes_cooldown = int(os.getenv("EPISODIC_COOLDOWN_MINUTES", "10"))
        max_per_day = int(os.getenv("EPISODIC_MAX_PER_DAY", "5"))

        ctx = config.get("configurable", {}).get("user_context") or {}
        tzname = ((ctx.get("locale_info", {}) or {}).get("time_zone") or "UTC") if isinstance(ctx, dict) else "UTC"
        try:
            import zoneinfo
            user_tz = zoneinfo.ZoneInfo(tzname)
        except Exception:
            user_tz = timezone.utc
        now_local = datetime.now(tz=user_tz)
        date_iso = now_local.date().isoformat()
        now_utc = datetime.now(tz=timezone.utc)

        session_store = get_session_store()
        sess = await session_store.get_session(thread_id) or {}
        ctrl = dict(sess.get("episodic_control") or {})
        if ctrl.get("day_iso") != date_iso:
            ctrl["day_iso"] = date_iso
            ctrl["count_today"] = 0
        ctrl["turns_since_last"] = int(ctrl.get("turns_since_last") or 0) + 1
        last_at_iso = ctrl.get("last_at_iso")
        last_dt = _parse_iso(last_at_iso) if isinstance(last_at_iso, str) else None
        recent_minutes_ok = not (last_dt and (now_utc - last_dt).total_seconds() < minutes_cooldown * 60)
        if ctrl.get("count_today", 0) >= max_per_day or ctrl["turns_since_last"] < turns_cooldown or not recent_minutes_ok:
            sess["episodic_control"] = ctrl
            await session_store.set_session(thread_id, sess)
            logger.info("episodic.decide: skip reason=cooldown_or_daily_cap")
            return {}

        N = int(os.getenv("EPISODIC_WINDOW_N", "10"))
        msgs = []
        for m in reversed(state["messages"]):
            role = getattr(m, "role", getattr(m, "type", None))
            if role not in ("user", "human", "assistant", "ai"):
                continue
            content = getattr(m, "content", None)
            if isinstance(content, str) and content.strip():
                msgs.append((role, content.strip()))
            if len(msgs) >= N:
                break
        msgs = list(reversed(msgs))
        if not msgs:
            return {}

        try:
            model_id = os.getenv("MEMORY_TINY_LLM_MODEL_ID", "amazon.nova-micro-v1:0")
            region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
            bedrock = boto3.client("bedrock-runtime", region_name=region)
            convo = "\n".join([f"{r.title()}: {t}" for r, t in msgs])[:2000]
            prompt = (
                "Summarize the interaction in 1–2 sentences focusing on what was discussed/decided/done. "
                "Exclude stable facts already known unless updated. Output strict JSON: "
                "{\"summary\": string, \"category\": string, \"importance\": 1..5}. "
                "Use concise neutral phrasing.\n\nConversation:\n" + convo + "\nJSON:"
            )
            body_payload = {"messages": [{"role": "user", "content": [{"text": prompt}]}], "inferenceConfig": {"temperature": 0.0, "topP": 0.1, "maxTokens": 128, "stopSequences": []}}
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
            parsed = {}
            if out_text:
                try:
                    parsed = json.loads(out_text)
                except Exception:
                    i, j = out_text.find("{"), out_text.rfind("}")
                    parsed = json.loads(out_text[i:j+1]) if i != -1 and j != -1 and j > i else {}
            epi_summary = str(parsed.get("summary") or "").strip()[:280]
            epi_category = str(parsed.get("category") or "Conversation_Summary").strip() or "Conversation_Summary"
            epi_importance = int(parsed.get("importance") or 1)
        except Exception:
            logger.exception("episodic.summarize.error")
            return {}
        if not epi_summary:
            return {}

        week = int(now_local.strftime("%V"))
        year = now_local.year
        human_summary = f"On {date_iso} (W{week}, {year}) {epi_summary}"

        store = get_store()
        namespace = (user_id, "episodic")
        merge_window_hours = int(os.getenv("EPISODIC_MERGE_WINDOW_HOURS", "48"))
        novelty_min = float(os.getenv("EPISODIC_NOVELTY_MIN", "0.90"))

        try:
            neighbors = store.search(namespace, query=human_summary, filter=None, limit=5)
        except Exception:
            neighbors = []

        best = neighbors[0] if neighbors else None
        if best and isinstance(getattr(best, "score", None), (int, float)):
            score_val = float(best.score or 0.0)
            ts = _parse_iso(getattr(best, "updated_at", "")) or _parse_iso(getattr(best, "created_at", ""))
            within_window = True
            if ts:
                within_window = (datetime.now(tz=timezone.utc) - ts) <= timedelta(hours=merge_window_hours)
            if score_val >= novelty_min and within_window:
                existing = store.get(namespace, getattr(best, "key", ""))
                if existing:
                    merged = dict(existing.value)
                    merged["last_accessed"] = _utc_now_iso()
                    if human_summary and len(human_summary) > len(merged.get("summary", "")):
                        merged["summary"] = human_summary
                    store.put(namespace, existing.key, merged, index=["summary"])  # re-embed
                    logger.info("episodic.merge: key=%s score=%.3f", existing.key, score_val)
                    if thread_id:
                        try:
                            queue = get_sse_queue(thread_id)
                            await queue.put({"event": "episodic.updated", "data": {"id": existing.key}})
                        except Exception:
                            pass
                    ctrl["turns_since_last"] = 0
                    ctrl["last_at_iso"] = now_utc.isoformat()
                    ctrl["count_today"] = int(ctrl.get("count_today") or 0) + 1
                    sess["episodic_control"] = ctrl
                    await session_store.set_session(thread_id, sess)
                    return {}

        candidate_id = uuid4().hex
        now = _utc_now_iso()
        value: dict[str, Any] = {
            "id": candidate_id,
            "user_id": user_id,
            "type": "episodic",
            "summary": human_summary,
            "category": epi_category,
            "tags": [],
            "source": "chat",
            "importance": epi_importance,
            "pinned": False,
            "created_at": now,
            "last_accessed": now,
        }
        store.put(namespace, candidate_id, value, index=["summary"])  # async context
        logger.info("episodic.create: id=%s", candidate_id)
        if thread_id:
            try:
                queue = get_sse_queue(thread_id)
                await queue.put({"event": "episodic.created", "data": {"id": candidate_id}})
            except Exception:
                pass
        ctrl["turns_since_last"] = 0
        ctrl["last_at_iso"] = now_utc.isoformat()
        ctrl["count_today"] = int(ctrl.get("count_today") or 0) + 1
        sess["episodic_control"] = ctrl
        await session_store.set_session(thread_id, sess)
        return {}
        logger.exception("episodic_capture.error")
        return {}


