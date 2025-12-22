from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Optional

from app.agents.onboarding.state import OnboardingState
from app.core.app_state import get_bedrock_runtime_client
from app.core.config import config
from app.models.user import UserContext
from app.services.external_context.user.mapping import map_ai_context_to_user_context, map_user_context_to_ai_context
from app.services.external_context.user.profile_metadata import build_profile_metadata_payload
from app.services.external_context.user.repository import ExternalUserRepository
from app.services.onboarding.context_patching import context_patching_service
from app.services.user_context_cache import get_user_context_cache

logger = logging.getLogger(__name__)


async def _profile_sync_from_memory(user_id: str, thread_id: Optional[str], value: dict[str, Any]) -> None:
    try:
        model_id = config.MEMORY_TINY_LLM_MODEL_ID
        bedrock = get_bedrock_runtime_client()
        from app.services.llm.prompt_loader import prompt_loader

        summary = str(value.get("summary") or "")[:500]
        category = str(value.get("category") or "")[:64]
        prompt = prompt_loader.load("profile_sync_extractor", category=category, summary=summary)
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
            contents = data.get("output", {}).get("message", {}).get("content", "")
            if isinstance(contents, list):
                for part in contents:
                    if isinstance(part, dict) and part.get("text"):
                        out_text += part.get("text", "")
            elif isinstance(contents, str):
                out_text = contents
        except Exception:
            out_text = data.get("outputText") or data.get("generation") or ""
        patch: dict[str, Any] = {}
        about_user: bool = False
        if out_text:
            try:
                parsed = json.loads(out_text)
            except Exception:
                i, j = out_text.find("{"), out_text.rfind("}")
                parsed = json.loads(out_text[i : j + 1]) if i != -1 and j != -1 and j > i else {}
            logger.info("profile_sync.proposed: %s", json.dumps(parsed)[:600])
            if isinstance(parsed, dict):
                raw_about = parsed.get("about_user")
                if isinstance(raw_about, bool):
                    about_user = raw_about
                elif isinstance(raw_about, str):
                    about_user = raw_about.strip().lower() == "true"
                else:
                    about_user = False
                if about_user:
                    for k in ("tone", "language", "city", "preferred_name", "income_band", "money_feelings"):
                        v = parsed.get(k)
                        if isinstance(v, str) and v.strip():
                            patch[k] = v.strip()

                    age = parsed.get("age")
                    if isinstance(age, (int, float)) and age > 0:
                        patch["age"] = int(age)

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

            identity_allowed = about_user

            if identity_allowed and patch.get("tone"):
                apply_patch["tone_preference"] = patch["tone"]
                changed["tone_preference"] = patch["tone"]

            goals_add = patch.get("goals_add")
            if isinstance(goals_add, list) and goals_add:
                existing = set(ctx.goals or [])
                merged = list(ctx.goals or []) + [g for g in goals_add if g not in existing]
                if merged != (ctx.goals or []):
                    apply_patch["personal_goals"] = merged
                    changed["goals"] = [g for g in merged if g not in (ctx.goals or [])]

            if identity_allowed:
                for k_src, k_dst in (
                    ("preferred_name", "preferred_name"),
                    ("city", "city"),
                    ("language", "language"),
                    ("income_band", "income_band"),
                ):
                    v = patch.get(k_src)
                    if isinstance(v, str) and v.strip():
                        apply_patch[k_dst] = v.strip()
                        changed[k_dst] = v.strip()

                if patch.get("age"):
                    apply_patch["age"] = patch["age"]
                    changed["age"] = patch["age"]

                if patch.get("money_feelings"):
                    apply_patch["money_feelings"] = [patch["money_feelings"]]
                    changed["money_feelings"] = [patch["money_feelings"]]

            if apply_patch:
                state = OnboardingState(user_id=uid, user_context=ctx)
                context_patching_service.apply_context_patch(state, "identity", apply_patch)

                body = map_user_context_to_ai_context(state.user_context)
                logger.info(f"[PROFILE_SYNC] Prepared external payload: {json.dumps(body, ensure_ascii=False)}")

                metadata_payload = build_profile_metadata_payload(state.user_context)
                task_defs: list[tuple[str, Awaitable[dict[str, Any] | None]]] = [
                    ("context_upsert", repo.upsert(state.user_context.user_id, body))
                ]
                if metadata_payload:
                    logger.info(
                        "[PROFILE_SYNC] Prepared profile metadata payload for user %s: %s",
                        state.user_context.user_id,
                        json.dumps(metadata_payload, ensure_ascii=False),
                    )
                    task_defs.append(
                        (
                            "profile_metadata_update",
                            repo.update_user_profile_metadata(state.user_context.user_id, metadata_payload),
                        )
                    )

                results = await asyncio.gather(*(coro for _, coro in task_defs), return_exceptions=True)

                for (task_name, _), result in zip(task_defs, results, strict=True):
                    if isinstance(result, Exception):
                        logger.warning(
                            "[PROFILE_SYNC] %s failed for user %s: %s",
                            task_name,
                            state.user_context.user_id,
                            result,
                        )
                        continue

                    if task_name == "context_upsert":
                        if result is not None:
                            logger.info(
                                "[PROFILE_SYNC] External API acknowledged update for user %s",
                                state.user_context.user_id,
                            )
                        else:
                            logger.warning(
                                "[PROFILE_SYNC] External API returned no body or 404 for user %s",
                                state.user_context.user_id,
                            )
                    elif task_name == "profile_metadata_update":
                        if result is not None:
                            logger.info(
                                "[PROFILE_SYNC] Profile metadata updated for user %s",
                                state.user_context.user_id,
                            )
                        else:
                            logger.warning(
                                "[PROFILE_SYNC] Profile metadata update returned no body for user %s",
                                state.user_context.user_id,
                            )

                try:
                    cache = get_user_context_cache()
                    cache.invalidate(state.user_context.user_id)
                    logger.info("[PROFILE_SYNC] Invalidated user context cache for user %s", state.user_context.user_id)
                except Exception as cache_err:
                    logger.warning(
                        "[PROFILE_SYNC] Failed to invalidate cache for user %s: %s",
                        state.user_context.user_id,
                        cache_err,
                    )

                logger.info("profile_sync.applied: %s", json.dumps(changed)[:400])
        except Exception as e:
            logger.warning(f"[PROFILE_SYNC] Failed to sync profile from memory: {e}")
    except Exception:
        logger.exception("profile_sync.error")
