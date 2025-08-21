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
from app.db.session import get_async_session
from app.repositories.session_store import get_session_store
from app.repositories.postgres.user_repository import PostgresUserRepository
from app.models.user import UserContext
from app.services.onboarding.context_patching import context_patching_service
from app.agents.onboarding.state import OnboardingState, OnboardingStep


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
    logger.debug("same_fact.prompt: %s", prompt[:600])
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
        logger.debug("same_fact.payload: %s", json.dumps(body_payload)[:600])
        res = bedrock.invoke_model(modelId=model_id, body=json.dumps(body_payload))
        body = res.get("body")
        txt = body.read().decode("utf-8") if hasattr(body, "read") else str(body)
        logger.debug("same_fact.raw: %s", txt[:600])
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
                {
                    "role": "user",
                    "content": [
                        {"text": prompt}
                    ],
                }
            ],
            "inferenceConfig": {
                "temperature": 0.2,
                "topP": 0.5,
                "maxTokens": 160,
                "stopSequences": [],
            },
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
        # Fallback: heuristic merge
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
        joined = f"{a} {b}"
        return joined[:280]


def _build_profile_line(ctx: dict[str, Any]) -> Optional[str]:
    if not isinstance(ctx, dict):
        return None
    name = ((ctx.get("identity", {}) or {}).get("preferred_name") or ctx.get("preferred_name") or None)
    tone = ctx.get("tone_preference") or (ctx.get("style", {}) or {}).get("tone") or None
    lang = ctx.get("language") or (ctx.get("locale_info", {}) or {}).get("language") or None
    city = ctx.get("city") or (ctx.get("location", {}) or {}).get("city") or None
    goals = ctx.get("goals") or []
    goals_str = ", ".join([str(g) for g in goals[:3] if isinstance(g, str)]) if isinstance(goals, list) else ""
    parts: list[str] = []
    if name:
        parts.append(f"name={name}")
    if city:
        parts.append(f"city={city}")
    if lang:
        parts.append(f"language={lang}")
    if tone:
        parts.append(f"tone={tone}")
    if goals_str:
        parts.append(f"goals={goals_str}")
    if not parts:
        return None
    core = "; ".join(parts)
    guidance = (
        " Use these details to personalize tone and examples. "
        "Do not restate this line verbatim. Do not override with assumptions. "
        "If the user contradicts this, prefer the latest user message."
    )
    return f"CONTEXT_PROFILE: {core}.{guidance}"


async def _profile_sync_from_memory(user_id: str, thread_id: Optional[str], value: dict[str, Any]) -> None:
    # Background: propose UserContext updates based on a single memory value
    try:
        model_id = os.getenv("MEMORY_TINY_LLM_MODEL_ID", "amazon.nova-micro-v1:0")
        region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
        bedrock = boto3.client("bedrock-runtime", region_name=region)
        summary = str(value.get("summary") or "")[:500]
        category = str(value.get("category") or "")[:64]
        prompt = (
            "Task: From the short summary, extract suggested profile updates.\n"
            "Output strict JSON with optional keys: {"
            "\"preferred_name\": string, \"pronouns\": string, \"language\": string, \"city\": string,"
            " \"tone\": string, \"goals_add\": [string]}.\n"
            f"Category: {category}\nSummary: {summary}\nJSON:"
        )
        body_payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
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
            out_text = data.get("outputText") or data.get("generation") or ""
        patch: dict[str, Any] = {}
        if out_text:
            try:
                parsed = json.loads(out_text)
            except Exception:
                i, j = out_text.find("{"), out_text.rfind("}")
                parsed = json.loads(out_text[i:j+1]) if i != -1 and j != -1 and j > i else {}
            logger.info("profile_sync.proposed: %s", json.dumps(parsed)[:600])
            if isinstance(parsed, dict):
                for k in ("tone", "language", "city", "preferred_name", "pronouns"):
                    v = parsed.get(k)
                    if isinstance(v, str) and v.strip():
                        patch[k] = v.strip()
                goals_add = parsed.get("goals_add")
                if isinstance(goals_add, list):
                    patch["goals_add"] = [str(x) for x in goals_add if isinstance(x, str) and x.strip()]

        # Build patch for ContextPatchingService (V1: apply all fields, no confirmations/SSE)

        async for db in get_async_session():
            repo = PostgresUserRepository(db)
            from uuid import UUID as _UUID
            uid = _UUID(user_id)
            ctx = await repo.get_by_id(uid) or UserContext(user_id=uid)

            apply_patch: dict[str, Any] = {}
            changed: dict[str, Any] = {}

            # Low-risk
            if patch.get("tone"):
                apply_patch["tone_preference"] = patch["tone"]
                changed["tone_preference"] = patch["tone"]

            goals_add = patch.get("goals_add")
            if isinstance(goals_add, list) and goals_add:
                existing = set(ctx.goals or [])
                merged = list(ctx.goals or []) + [g for g in goals_add if g not in existing]
                if merged != (ctx.goals or []):
                    apply_patch["personal_goals"] = merged
                    changed["goals"] = [g for g in merged if g not in (ctx.goals or [])]

            # Sensitive: apply directly in V1 (no confirmation flow)
            for k_src, k_dst in (
                ("preferred_name", "preferred_name"),
                ("pronouns", "pronouns"),
                ("city", "city"),
                ("language", "language"),
            ):
                v = patch.get(k_src)
                if isinstance(v, str) and v.strip():
                    apply_patch[k_dst] = v.strip()
                    changed[k_dst] = v.strip()

            if apply_patch:
                state = OnboardingState(user_id=uid, user_context=ctx)
                context_patching_service.apply_context_patch(state, OnboardingStep.IDENTITY, apply_patch)
                await repo.upsert(state.user_context)
                logger.info("profile_sync.applied: %s", json.dumps(changed)[:400])
    except Exception:
        logger.exception("profile_sync.error")



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
        prompt = (
            f"{instr}\nRecentMessages:\n{text[:1000]}\nJSON:"
        )
        logger.debug("trigger.prompt: %s", prompt[:600])
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
            logger.debug("trigger.payload: %s", json.dumps(body_payload)[:600])
            res = bedrock.invoke_model(modelId=model_id, body=json.dumps(body_payload))
            body = res.get("body")
            txt = body.read().decode("utf-8") if hasattr(body, "read") else str(body)
            logger.debug("trigger.raw: %s", txt[:600])
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
            logger.debug("trigger.parsed: %s", out)
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
        # No new memory: still inject a profile line so the model stays grounded
        # TODO: Long-term move this dynamic context into a per-turn system parameter binding to avoid message echoing.
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

    # Entry node enforces semantic-only writes; skip episodic creations here
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
            namespace = (user_id, "semantic")
            # Neighbor search for potential merge
            try:
                merge_topk = int(os.getenv("MEMORY_MERGE_TOPK", "5"))
                neighbors = store.search(namespace, query=summary, filter={"category": category}, limit=merge_topk)
            except Exception:
                neighbors = []
            logger.info(
                "memory.search: id=%s ns=%s neighbors=%d",
                candidate_id,
                "/".join(namespace),
                len(neighbors),
            )

            # Thresholds (semantic-only at entry)
            auto_update = float(os.getenv("MEMORY_MERGE_AUTO_UPDATE", "0.85"))
            check_low = float(os.getenv("MEMORY_MERGE_CHECK_LOW", "0.60"))
            merge_mode = (os.getenv("MEMORY_MERGE_MODE", "recreate") or "recreate").lower()
            merge_window_hours = int(os.getenv("EPISODIC_MERGE_WINDOW_HOURS", "72"))
            best = neighbors[0] if neighbors else None
            did_update = False
            queue = get_sse_queue(thread_id) if thread_id else None
            if best and isinstance(getattr(best, "score", None), (int, float)):
                score_val = float(best.score or 0.0)
                # Recency not used for semantic updates in entry node
                recency_ok = True
                logger.info(
                    "memory.match: id=%s best_key=%s score=%.3f recency_ok=%s auto=%.2f low=%.2f",
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

                def do_recreate(existing_key: str, existing_item: Any) -> None:
                    existing = store.get(namespace, existing_key)
                    if not existing:
                        return
                    existing_summary = str(existing.value.get("summary") or "")
                    composed = _compose_summaries(existing_summary, summary, category)
                    new_id = uuid4().hex
                    new_val = dict(candidate_value)
                    new_val["id"] = new_id
                    # compose tags/pinned/importance from existing + candidate
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
                    # Create new enriched memory first
                    store.put(namespace, new_id, new_val, index=["summary"])  # embed
                    # Always delete the old memory on recreate
                    store.delete(namespace, existing_key)

                if score_val >= auto_update and recency_ok:
                    if merge_mode == "recreate":
                        do_recreate(best.key, best)
                        did_update = True
                        logger.info(
                            "memory.recreate: mode=auto id=%s from=%s score=%.3f",
                            candidate_id,
                            best.key,
                            score_val,
                        )
                    else:
                        do_update(best.key)
                        did_update = True
                        logger.info(
                            "memory.update: mode=auto id=%s into=%s score=%.3f",
                            candidate_id,
                            best.key,
                            score_val,
                        )
                    if queue:
                        try:
                            await queue.put(
                                {
                                    "event": "memory.updated",
                                    "data": {"id": getattr(best, "key", None), "type": mem_type, "category": (getattr(best, "value", {}) or {}).get("category")},
                                }
                            )
                        except Exception:
                            pass
                else:
                    # Expand dedup to top-N neighbors
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
                        logger.info(
                            "memory.classify: id=%s cand_into=%s score=%.3f result_same=%s",
                            candidate_id,
                            getattr(n, "key", ""),
                            s,
                            same,
                        )
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
                                    await queue.put(
                                        {
                                            "event": "memory.updated",
                                            "data": {
                                                "id": getattr(n, "key", ""),
                                                "type": mem_type,
                                                "category": (getattr(n, "value", {}) or {}).get("category"),
                                            },
                                        }
                                    )
                                except Exception:
                                    pass
                            break
            if not did_update:
                # Respect minimum importance for creation (updates can still happen above)
                if int(candidate_value.get("importance") or 1) < min_importance:
                    logger.info("memory.skip: below_min_importance=%s", min_importance)
                else:
                    store.put(namespace, candidate_id, candidate_value, index=["summary"])  # async context
                    logger.info(
                        "memory.create: id=%s type=%s category=%s",
                        candidate_id,
                        "semantic",
                        category,
                    )
                    # Background profile sync from new memory
                    asyncio.create_task(_profile_sync_from_memory(user_id, thread_id, candidate_value))
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
    # Also inject current profile line alongside the candidate to ground the turn
    # TODO: Long-term move this dynamic context into a per-turn system parameter binding to avoid message echoing.
    ctx = config.get("configurable", {}).get("user_context") or {}
    prof = _build_profile_line(ctx) if isinstance(ctx, dict) else None
    return ({"messages": [HumanMessage(content=prof)]} if prof else {})


async def memory_context(state: MessagesState, config: RunnableConfig) -> dict:
    messages = state["messages"]
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
    user_id = config.get("configurable", {}).get("user_id")
    if not user_id:
        return {}

    bullets: list[str] = []
    # Retrieval knobs
    topk = int(os.getenv("MEMORY_CONTEXT_TOPK", "24"))
    topn = int(os.getenv("MEMORY_CONTEXT_TOPN", "5"))
    weights_raw = os.getenv("MEMORY_RERANK_WEIGHTS", "sim=0.55,imp=0.20,recency=0.15,pinned=0.10")
    def _parse_weights(s: str) -> dict[str, float]:
        out: dict[str, float] = {"sim": 0.55, "imp": 0.20, "recency": 0.15, "pinned": 0.10}
        try:
            for part in s.split(","):
                if not part.strip():
                    continue
                k, v = part.split("=")
                out[k.strip()] = float(v.strip())
        except Exception:
            pass
        return out
    w = _parse_weights(weights_raw)
    try:
        store = get_store()
        query_text = (user_text or "").strip() or "personal profile"
        logger.info(
            "memory_context.query: user_id=%s query=%s", user_id, (query_text[:200])
        )
        sem = store.search((user_id, "semantic"), query=query_text, filter=None, limit=topk)
        epi = store.search((user_id, "episodic"), query=query_text, filter=None, limit=max(3, topk//2))
        logger.info("memory_context.results: sem=%d epi=%d", len(sem or []), len(epi or []))

        # Local rerank: similarity + importance + recency + pinned
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
            return w["sim"]*sim + w["imp"]*(imp/5.0) + w["recency"]*recency + w["pinned"]*pinned

        # Hybrid selection: top 2 by raw similarity, then fill up to 5 via reranked list
        raw_sorted = sorted(sem, key=lambda it: float(getattr(it, "score", 0.0) or 0.0), reverse=True)
        pre_raw = raw_sorted[:2]
        reranked_full = sorted(sem, key=_score, reverse=True)
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
        try:
            sem_preview = [
                {
                    "key": getattr(it, "key", None),
                    "score": float(getattr(it, "score", 0.0) or 0.0),
                    "category": (getattr(it, "value", {}) or {}).get("category"),
                    "summary_preview": ((getattr(it, "value", {}) or {}).get("summary") or "")[:80],
                }
                for it in merged_sem[:topn]
            ]
            logger.info("memory_context.sem.top: %s", json.dumps(sem_preview))
        except Exception:
            pass

        epi_sorted = sorted(epi, key=_score, reverse=True)[:max(1, max(1, topn//2))]
        for it in epi_sorted[:2]:
            cat = it.value.get("category")
            txt = it.value.get("summary")
            if txt:
                bullets.append(f"[{cat}] {txt}")
        for it in merged_sem[:topn]:
            cat = it.value.get("category")
            txt = it.value.get("summary")
            if txt:
                bullets.append(f"[{cat}] {txt}")
        try:
            logger.info("memory_context.bullets.count: %d", len(bullets))
        except Exception:
            pass
    except Exception:
        pass

    if not bullets:
        return {}
    # Add current local time (user timezone if available) as a context bullet
    try:
        ctx = config.get("configurable", {}).get("user_context") or {}
        tzname = ((ctx.get("locale_info", {}) or {}).get("time_zone") or "UTC") if isinstance(ctx, dict) else "UTC"
        try:
            import zoneinfo
            user_tz = zoneinfo.ZoneInfo(tzname)
        except Exception:
            user_tz = timezone.utc
        now_local = datetime.now(tz=user_tz)
        date_bullet = f"Now: {now_local.strftime('%Y-%m-%d %H:%M %Z')}"
    except Exception:
        date_bullet = None
    all_bullets = ([date_bullet] if date_bullet else []) + bullets
    context_str = "Relevant context for tailoring this turn:\n- " + "\n- ".join(all_bullets)
    return {"messages": [HumanMessage(content=context_str)]}


async def episodic_capture(state: MessagesState, config: RunnableConfig) -> dict:
    try:
        user_id = config.get("configurable", {}).get("user_id")
        thread_id = config.get("configurable", {}).get("thread_id")
        if not user_id:
            return {}

        # Cooldown / caps using session state (no extra metadata or listing)
        turns_cooldown = int(os.getenv("EPISODIC_COOLDOWN_TURNS", "3"))
        minutes_cooldown = int(os.getenv("EPISODIC_COOLDOWN_MINUTES", "10"))
        max_per_day = int(os.getenv("EPISODIC_MAX_PER_DAY", "5"))

        # Determine user's timezone and current local day for daily cap
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
        # Reset daily counter if day changed
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

        # Collect last N human+assistant messages for summarization
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

        # Summarize via tiny LLM (Nova Micro)
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

        # Derive week/year for the human text only (no extra metadata stored)
        week = int(now_local.strftime("%V"))
        year = now_local.year

        # Compose human-friendly summary with date bucket (no extra metadata stored)
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
                    # Update cooldown control on merge
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
        # Update cooldown control on create
        ctrl["turns_since_last"] = 0
        ctrl["last_at_iso"] = now_utc.isoformat()
        ctrl["count_today"] = int(ctrl.get("count_today") or 0) + 1
        sess["episodic_control"] = ctrl
        await session_store.set_session(thread_id, sess)
        return {}
    except Exception:
        logger.exception("episodic.error")
        return {}

