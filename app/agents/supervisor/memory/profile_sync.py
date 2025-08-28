from __future__ import annotations

import json
import logging
from typing import Any, Optional

import boto3

from app.agents.onboarding.state import OnboardingState, OnboardingStep
from app.models.user import UserContext
from app.services.external_context.client import ExternalUserRepository
from app.services.external_context.mapping import map_ai_context_to_user_context, map_user_context_to_ai_context
from app.services.onboarding.context_patching import context_patching_service

logger = logging.getLogger(__name__)


async def _profile_sync_from_memory(user_id: str, thread_id: Optional[str], value: dict[str, Any]) -> None:

    try:
        model_id = config.MEMORY_TINY_LLM_MODEL_ID
        region = config.AWS_REGION
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

        try:
            from uuid import UUID as _UUID
            uid = _UUID(user_id)

            repo = ExternalUserRepository()
            external_ctx = await repo.get_by_id(uid)

            ctx = UserContext(user_id=uid)
            if external_ctx:
                ctx = map_ai_context_to_user_context(external_ctx, ctx)
                logger.info(f"[PROFILE_SYNC] Loaded external AI Context for user: {uid}")
            else:
                logger.info(f"[PROFILE_SYNC] No external AI Context found for user: {uid}")

            apply_patch: dict[str, Any] = {}
            changed: dict[str, Any] = {}

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

            for k_src, k_dst in (("preferred_name", "preferred_name"), ("pronouns", "pronouns"), ("city", "city"), ("language", "language")):
                v = patch.get(k_src)
                if isinstance(v, str) and v.strip():
                    apply_patch[k_dst] = v.strip()
                    changed[k_dst] = v.strip()

            if apply_patch:
                state = OnboardingState(user_id=uid, user_context=ctx)
                context_patching_service.apply_context_patch(state, OnboardingStep.IDENTITY, apply_patch)

                body = map_user_context_to_ai_context(state.user_context)
                logger.info(f"[PROFILE_SYNC] Prepared external payload: {json.dumps(body, ensure_ascii=False)}")
                resp = await repo.upsert(state.user_context.user_id, body)
                if resp is not None:
                    logger.info(f"[PROFILE_SYNC] External API acknowledged update for user {state.user_context.user_id}")
                else:
                    logger.warning(f"[PROFILE_SYNC] External API returned no body or 404 for user {state.user_context.user_id}")

                logger.info("profile_sync.applied: %s", json.dumps(changed)[:400])
        except Exception as e:
            logger.warning(f"[PROFILE_SYNC] Failed to sync profile from memory: {e}")
    except Exception:
        logger.exception("profile_sync.error")


