from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any
from uuid import uuid4

import boto3
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_store
from langgraph.graph import MessagesState

from app.core.app_state import get_sse_queue
from .utils import _utc_now_iso, _build_profile_line

logger = logging.getLogger(__name__)


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
    try:
        body_payload = {
            "messages": [
                {"role": "user", "content": [{"text": prompt}]}
            ],
            "inferenceConfig": {"temperature": 0.0, "topP": 0.1, "maxTokens": 96, "stopSequences": []},
        }
        res = bedrock.invoke_model(modelId=model_id, body=json.dumps(body_payload))
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
    model_id = os.getenv("MEMORY_TINY_LLM_MODEL_ID", "amazon.nova-micro-v1:0")
    region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
    bedrock = boto3.client("bedrock-runtime", region_name=region)
    prompt = (
        "Task: Combine two short summaries about the SAME user fact into one concise statement.\n"
        "- Keep it neutral, third person, and include both details without redundancy.\n"
        "- 1–2 sentences, max 280 characters.\n"
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
        res = bedrock.invoke_model(modelId=model_id, body=json.dumps(body_payload))
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
    combined_text = "\n".join(reversed(recent_user_texts))

    def _trigger_decide(text: str) -> dict[str, Any]:
        model_id = os.getenv("MEMORY_TINY_LLM_MODEL_ID", "amazon.nova-micro-v1:0")
        region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
        bedrock = boto3.client("bedrock-runtime", region_name=region)
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
            "- Choose category from: [" + allowed_categories + "].\n"
            "- summary must be 1–2 sentences, concise and neutral (third person).\n"
            "- Output ONLY strict JSON: {\"should_create\": bool, \"type\": \"semantic\", \"category\": string, \"summary\": string, \"importance\": 1..5}.\n"
            "\n"
            "Examples (create):\n"
            "- Input: 'Please remember my name is Ana' -> {\"should_create\": true, \"type\": \"semantic\", \"category\": \"Personal\", \"summary\": \"User’s preferred name is Ana.\", \"importance\": 2}\n"
            "- Input: 'My cat just turned 4' -> {\"should_create\": true, \"type\": \"semantic\", \"category\": \"Personal\", \"summary\": \"User’s cat is 4 years old.\", \"importance\": 3}\n"
            "- Input: 'I prefer email over phone calls' -> {\"should_create\": true, \"type\": \"semantic\", \"category\": \"Personal\", \"summary\": \"User prefers email communication over calls.\", \"importance\": 2}\n"
            "- Input: 'We’re saving for a house down payment this year' -> {\"should_create\": true, \"type\": \"semantic\", \"category\": \"Finance\", \"summary\": \"User is saving for a house down payment this year.\", \"importance\": 3}\n"
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
            res = bedrock.invoke_model(modelId=model_id, body=json.dumps(body_payload))
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
        except Exception:
            logger.exception("trigger.error")
            return {"should_create": False}

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
    summary = str(trigger.get("summary") or recent_user_texts[0] or combined_text).strip()[:280]
    min_importance = int(os.getenv("MEMORY_SEMANTIC_MIN_IMPORTANCE", "1"))

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

    if thread_id:
        try:
            queue = get_sse_queue(thread_id)
            await queue.put({"event": "memory.candidate", "data": {"id": candidate_id, "type": mem_type, "category": category, "summary": summary}})
        except Exception:
            pass

    async def do_write() -> None:
        try:
            store = get_store()
            namespace = (user_id, "semantic")
            try:
                merge_topk = int(os.getenv("MEMORY_MERGE_TOPK", "5"))
                neighbors = store.search(namespace, query=summary, filter={"category": category}, limit=merge_topk)
            except Exception:
                neighbors = []
            logger.info("memory.search: id=%s ns=%s neighbors=%d", candidate_id, "/".join(namespace), len(neighbors))

            auto_update = float(os.getenv("MEMORY_MERGE_AUTO_UPDATE", "0.85"))
            check_low = float(os.getenv("MEMORY_MERGE_CHECK_LOW", "0.60"))
            merge_mode = (os.getenv("MEMORY_MERGE_MODE", "recreate") or "recreate").lower()
            best = neighbors[0] if neighbors else None
            did_update = False
            queue = get_sse_queue(thread_id) if thread_id else None
            if best and isinstance(getattr(best, "score", None), (int, float)):
                score_val = float(best.score or 0.0)
                recency_ok = True
                logger.info("memory.match: id=%s best_key=%s score=%.3f recency_ok=%s auto=%.2f low=%.2f", candidate_id, getattr(best, "key", ""), score_val, recency_ok, auto_update, check_low)

                def do_update(existing_key: str) -> None:
                    existing = store.get(namespace, existing_key)
                    if not existing:
                        return
                    merged = dict(existing.value)
                    merged["last_accessed"] = _utc_now_iso()
                    if summary and len(summary) > len(merged.get("summary", "")):
                        merged["summary"] = summary
                    store.put(namespace, existing_key, merged, index=["summary"])  # re-embed

                def do_recreate(existing_key: str, existing_item: Any) -> None:
                    existing = store.get(namespace, existing_key)
                    if not existing:
                        return
                    existing_summary = str(existing.value.get("summary") or "")
                    composed = _compose_summaries(existing_summary, summary, category)
                    new_id = uuid4().hex
                    new_val = dict(candidate_value)
                    new_val["id"] = new_id
                    try:
                        prev_imp = int(existing.value.get("importance") or 1)
                    except Exception:
                        prev_imp = 1
                    new_val["importance"] = max(prev_imp, int(candidate_value.get("importance") or 1))
                    new_val["pinned"] = bool(existing.value.get("pinned")) or bool(candidate_value.get("pinned"))
                    try:
                        prev_tags = existing.value.get("tags") or []
                        cand_tags = candidate_value.get("tags") or []
                        if isinstance(prev_tags, list) and isinstance(cand_tags, list):
                            new_val["tags"] = list({*(t for t in prev_tags if isinstance(t, str)), *(t for t in cand_tags if isinstance(t, str))})
                    except Exception:
                        pass
                    new_val["summary"] = composed
                    store.put(namespace, new_id, new_val, index=["summary"])  # embed
                    store.delete(namespace, existing_key)

                if score_val >= auto_update and recency_ok:
                    if merge_mode == "recreate":
                        do_recreate(best.key, best)
                        did_update = True
                        logger.info("memory.recreate: mode=auto id=%s from=%s score=%.3f", candidate_id, best.key, score_val)
                    else:
                        do_update(best.key)
                        did_update = True
                        logger.info("memory.update: mode=auto id=%s into=%s score=%.3f", candidate_id, best.key, score_val)
                    if queue:
                        try:
                            await queue.put({"event": "memory.updated", "data": {"id": getattr(best, "key", None), "type": mem_type, "category": (getattr(best, "value", {}) or {}).get("category")}})
                        except Exception:
                            pass
                else:
                    sorted_neigh = sorted(neighbors, key=lambda it: float(getattr(it, "score", 0.0) or 0.0), reverse=True)
                    for n in sorted_neigh:
                        s = float(getattr(n, "score", 0.0) or 0.0)
                        if s < check_low:
                            break
                        same = _same_fact_classify(
                            existing_summary=str((getattr(n, "value", {}) or {}).get("summary", "")),
                            candidate_summary=summary,
                            category=category,
                        )
                        logger.info("memory.classify: id=%s cand_into=%s score=%.3f result_same=%s", candidate_id, getattr(n, "key", ""), s, same)
                        if same:
                            if merge_mode == "recreate":
                                do_recreate(getattr(n, "key", ""), n)
                                logger.info("memory.recreate: mode=classified id=%s from=%s", candidate_id, getattr(n, "key", ""))
                            else:
                                do_update(getattr(n, "key", ""))
                                logger.info("memory.update: mode=classified id=%s into=%s", candidate_id, getattr(n, "key", ""))
                            did_update = True
                            if queue:
                                try:
                                    await queue.put({"event": "memory.updated", "data": {"id": getattr(n, "key", ""), "type": mem_type, "category": (getattr(n, "value", {}) or {}).get("category")}})
                                except Exception:
                                    pass
                            break
            if not did_update:
                if int(candidate_value.get("importance") or 1) < min_importance:
                    logger.info("memory.skip: below_min_importance=%s", min_importance)
                else:
                    store.put(namespace, candidate_id, candidate_value, index=["summary"])  # async context
                    logger.info("memory.create: id=%s type=%s category=%s", candidate_id, "semantic", category)
                    asyncio.create_task(_profile_sync_from_memory(user_id, thread_id, candidate_value))
                    if queue:
                        try:
                            await queue.put({"event": "memory.created", "data": {"id": candidate_id, "type": mem_type, "category": category}})
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

    # import placed here to avoid circular import during module init
    from .profile_sync import _profile_sync_from_memory  # type: ignore

    asyncio.create_task(do_write())
    ctx = config.get("configurable", {}).get("user_context") or {}
    prof = _build_profile_line(ctx) if isinstance(ctx, dict) else None
    return ({"messages": [HumanMessage(content=prof)]} if prof else {})


