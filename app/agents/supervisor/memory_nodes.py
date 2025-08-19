from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
from uuid import uuid4

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_store
from langgraph.graph import MessagesState

from app.core.app_state import get_sse_queue
import os
import json
import boto3
import logging


logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _same_fact_classify(existing_summary: str, candidate_summary: str, category: str) -> bool:
    model_id = os.getenv("MEMORY_TINY_LLM_MODEL_ID", "amazon.nova-micro-v1:0")
    region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
    bedrock = boto3.client("bedrock-runtime", region_name=region)
    prompt = (
        "Task: Decide if two short summaries express the SAME FACT.\n"
        "Guidance: Consider meaning, not wording. If they describe the same stable fact/preference, it's the same.\n"
        "Output: strict JSON: {\"same_fact\": true|false}. No other text.\n"
        f"Category: {category[:64]}\n"
        f"Existing: {existing_summary[:500]}\n"
        f"Candidate: {candidate_summary[:500]}\n"
    )
    logger.info("same_fact.prompt: %s", prompt[:600])
    try:
        body_payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"text": prompt}
                    ],
                }
            ],
            "inferenceConfig": {
                "temperature": 0.0,
                "topP": 0.1,
                "maxTokens": 96,
                "stopSequences": [],
            },
        }
        logger.info("same_fact.payload: %s", json.dumps(body_payload)[:600])
        res = bedrock.invoke_model(modelId=model_id, body=json.dumps(body_payload))
        body = res.get("body")
        txt = body.read().decode("utf-8") if hasattr(body, "read") else str(body)
        logger.info("same_fact.raw: %s", txt[:600])
        data = json.loads(txt)
        # Extract assistant text from chat-style output
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
            start = out_text.find("{")
            end = out_text.rfind("}")
            if start != -1 and end != -1 and end > start:
                out = json.loads(out_text[start : end + 1])
            else:
                return False
        result = bool(out.get("same_fact") is True)
        logger.info("same_fact.result: %s", result)
        return result
    except Exception:
        logger.exception("same_fact.error")
        return False


async def memory_hotpath(state: MessagesState, config: RunnableConfig) -> dict:
    messages = state["messages"]
    recent_user_texts: list[str] = []
    for m in reversed(messages):
        role = getattr(m, "role", getattr(m, "type", None))
        if role in ("user", "human"):
            content = getattr(m, "content", None)
            if isinstance(content, str) and content.strip():
                recent_user_texts.append(content.strip())
                if len(recent_user_texts) >= 3:
                    break
    if not recent_user_texts:
        return {}
    # Combine last 2–3 user turns (most recent first in list); reverse to chronological
    combined_text = "\n".join(reversed(recent_user_texts))

    # Trigger decision via tiny LLM (no heuristics)
    def _trigger_decide(text: str) -> dict[str, Any]:
        model_id = os.getenv("MEMORY_TINY_LLM_MODEL_ID", "amazon.nova-micro-v1:0")
        region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
        bedrock = boto3.client("bedrock-runtime", region_name=region)
        allowed_categories = (
            "Finance, Budget, Goals, Personal, Education, Conversation_Summary, Other"
        )
        instr = (
            "You classify whether to CREATE a user memory from recent user messages.\n"
            "Rules:\n"
            "- If the user explicitly asks to 'remember' something, set should_create=true.\n"
            "- Use type=semantic for stable facts/preferences/identity; type=episodic for time-bound events.\n"
            "- Choose category from: [" + allowed_categories + "].\n"
            "- summary must be 1–2 sentences, concise and neutral.\n"
            "Output ONLY strict JSON: {\"should_create\": bool, \"type\": \"semantic|episodic\", \"category\": string, \"summary\": string, \"importance\": 1..5}.\n"
            "Examples:\n"
            "Input: 'Hi my name is Joaquin, remember that' -> {\"should_create\": true, \"type\": \"semantic\", \"category\": \"Personal\", \"summary\": \"User's name is Joaquin.\", \"importance\": 2}\n"
            "Input: 'Book an appointment' -> {\"should_create\": false}\n"
        )
        prompt = (
            f"{instr}\nRecentMessages:\n{text[:1000]}\nJSON:"
        )
        logger.info("trigger.prompt: %s", prompt[:600])
        try:
            body_payload = {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"text": prompt}
                        ],
                    }
                ],
                "inferenceConfig": {
                    "temperature": 0.0,
                    "topP": 0.1,
                    "maxTokens": 96,
                    "stopSequences": [],
                },
            }
            logger.info("trigger.payload: %s", json.dumps(body_payload)[:600])
            res = bedrock.invoke_model(modelId=model_id, body=json.dumps(body_payload))
            body = res.get("body")
            txt = body.read().decode("utf-8") if hasattr(body, "read") else str(body)
            logger.info("trigger.raw: %s", txt[:600])
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
                start = out_text.find("{")
                end = out_text.rfind("}")
                if start != -1 and end != -1 and end > start:
                    out = json.loads(out_text[start : end + 1])
                else:
                    return {"should_create": False}
            if not isinstance(out, dict):
                return {"should_create": False}
            logger.info("trigger.parsed: %s", out)
            return out
        except Exception:
            logger.exception("trigger.error")
            return {"should_create": False}

    trigger = _trigger_decide(combined_text)
    logger.info("memory_hotpath.trigger llm: %s", trigger)
    if not trigger.get("should_create"):
        return {}

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
    summary = str(trigger.get("summary") or recent_user_texts[0] or combined_text).strip()[:280]
    candidate_id = uuid4().hex
    now = _utc_now_iso()
    candidate_value: dict[str, Any] = {
        "id": candidate_id,
        "user_id": user_id,
        "type": mem_type,
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

    # Emit candidate SSE
    if thread_id:
        try:
            queue = get_sse_queue(thread_id)
            await queue.put(
                {
                    "event": "memory.candidate",
                    "data": {
                        "id": candidate_id,
                        "type": mem_type,
                        "category": category,
                        "summary": summary,
                    },
                }
            )
        except Exception:
            pass

    async def do_write() -> None:
        try:
            store = get_store()
            namespace = (user_id, mem_type)
            # Neighbor search for potential merge
            try:
                neighbors = store.search(namespace, query=summary, filter={"category": category}, limit=5)
            except Exception:
                neighbors = []
            logger.info(
                "memory_hotpath.search: id=%s ns=%s neighbors=%d",
                candidate_id,
                "/".join(namespace),
                len(neighbors),
            )

            # Thresholds
            auto_update = 0.90 if mem_type == "semantic" else 0.92
            check_low = 0.80 if mem_type == "semantic" else 0.85
            merge_window_hours = int(os.getenv("EPISODIC_MERGE_WINDOW_HOURS", "72"))
            best = neighbors[0] if neighbors else None
            did_update = False
            queue = get_sse_queue(thread_id) if thread_id else None
            if best and isinstance(getattr(best, "score", None), (int, float)):
                score_val = float(best.score or 0.0)
                # Episodic recency check
                recency_ok = True
                if mem_type == "episodic":
                    ts = _parse_iso(best.created_at)
                    if ts is None or datetime.now(tz=timezone.utc) - ts > timedelta(hours=merge_window_hours):
                        recency_ok = False
                logger.info(
                    "memory_hotpath.best: id=%s best_key=%s score=%.3f recency_ok=%s auto=%.2f low=%.2f",
                    candidate_id,
                    getattr(best, "key", ""),
                    score_val,
                    recency_ok,
                    auto_update,
                    check_low,
                )

                def do_update(existing_key: str) -> None:
                    existing = store.get(namespace, existing_key)
                    if not existing:
                        return
                    merged = dict(existing.value)
                    merged["last_accessed"] = _utc_now_iso()
                    if summary and len(summary) > len(merged.get("summary", "")):
                        merged["summary"] = summary
                    store.put(namespace, existing_key, merged, index=["summary"])  # re-embed

                if score_val >= auto_update and (mem_type == "semantic" or recency_ok):
                    do_update(best.key)
                    did_update = True
                    logger.info(
                        "memory_hotpath.action: UPDATE (auto) id=%s into=%s",
                        candidate_id,
                        best.key,
                    )
                    if queue:
                        try:
                            await queue.put(
                                {
                                    "event": "memory.updated",
                                    "data": {"id": best.key, "type": mem_type, "category": best.value.get("category")},
                                }
                            )
                        except Exception:
                            pass
                elif score_val >= check_low and (mem_type == "semantic" or recency_ok):
                    # Tiny LLM check for same_fact
                    same = _same_fact_classify(
                        existing_summary=str(best.value.get("summary", "")),
                        candidate_summary=summary,
                        category=category,
                    )
                    logger.info(
                        "memory_hotpath.classify: id=%s best_key=%s score=%.3f result_same=%s",
                        candidate_id,
                        getattr(best, "key", ""),
                        score_val,
                        same,
                    )
                    if same:
                        do_update(best.key)
                        did_update = True
                        logger.info(
                            "memory_hotpath.action: UPDATE (classified) id=%s into=%s",
                            candidate_id,
                            best.key,
                        )
                        if queue:
                            try:
                                await queue.put(
                                    {
                                        "event": "memory.updated",
                                        "data": {
                                            "id": best.key,
                                            "type": mem_type,
                                            "category": best.value.get("category"),
                                        },
                                    }
                                )
                            except Exception:
                                pass
            if not did_update:
                store.put(namespace, candidate_id, candidate_value, index=["summary"])  # async context
                logger.info(
                    "memory_hotpath.action: CREATE id=%s type=%s category=%s",
                    candidate_id,
                    mem_type,
                    category,
                )
                if queue:
                    try:
                        await queue.put(
                            {
                                "event": "memory.created",
                                "data": {"id": candidate_id, "type": mem_type, "category": category},
                            }
                        )
                    except Exception:
                        pass
        except Exception:
            logger.exception("memory_hotpath.error: id=%s", candidate_id)
            if thread_id:
                try:
                    queue = get_sse_queue(thread_id)
                    await queue.put({"event": "memory.error", "data": {"id": candidate_id}})
                except Exception:
                    pass

    asyncio.create_task(do_write())
    return {}


async def memory_context(state: MessagesState, config: RunnableConfig) -> dict:
    messages = state["messages"]
    user_text: str | None = None
    for m in reversed(messages):
        role = getattr(m, "role", getattr(m, "type", None))
        if role in ("user", "human"):
            user_text = getattr(m, "content", None)
            break
    user_id = config.get("configurable", {}).get("user_id")
    if not user_id:
        return {}

    bullets: list[str] = []
    try:
        store = get_store()
        sem = store.search((user_id, "semantic"), query=user_text or "", filter=None, limit=5) if user_text else []
        epi = store.search((user_id, "episodic"), query=user_text or "", filter=None, limit=3) if user_text else []
        for it in epi[:2]:
            cat = it.value.get("category")
            txt = it.value.get("summary")
            if txt:
                bullets.append(f"Recent: [{cat}] {txt}")
        for it in sem[:3]:
            cat = it.value.get("category")
            txt = it.value.get("summary")
            if txt:
                bullets.append(f"Profile: [{cat}] {txt}")
    except Exception:
        pass

    if not bullets:
        return {}
    context_str = "Relevant context for tailoring this turn:\n- " + "\n- ".join(bullets)
    # Use HumanMessage to avoid Anthropic requirement: system must be first in list
    return {"messages": [HumanMessage(content=context_str)]}


