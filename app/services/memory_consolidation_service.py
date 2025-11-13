from __future__ import annotations

import asyncio
import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.app_state import get_bedrock_runtime_client
from app.core.config import config
from app.repositories.s3_vectors_store import SearchItem
from app.services.llm.prompt_loader import prompt_loader
from app.services.memory.store_factory import create_s3_vectors_store_from_env
from app.services.nudges.evaluator import iter_active_users

logger = logging.getLogger(__name__)


@dataclass
class ConsolidationStats:
    total_users_processed: int = 0
    total_memories_scanned: int = 0
    total_memories_merged: int = 0
    total_merge_groups: int = 0
    errors: list[str] = field(default_factory=list)


class MemoryConsolidationService:
    MAX_CONCURRENT_USERS = 10
    SEARCH_LIMIT = 20

    def __init__(self) -> None:
        self._store = create_s3_vectors_store_from_env()
        self._bedrock = get_bedrock_runtime_client()
        self._similarity_threshold = 0.65
        self._llm_model_id = config.MEMORY_TINY_LLM_MODEL_ID
        self._max_concurrent_users = self.MAX_CONCURRENT_USERS
        self._search_limit = self.SEARCH_LIMIT

    async def consolidate_memories(
        self,
        user_id: str | None = None,
        memory_type: str | None = None
    ) -> dict[str, Any]:
        logger.info(f"Starting memory consolidation - user_id: {user_id}, memory_type: {memory_type}")

        if user_id:
            user_ids = [user_id]
        else:
            user_ids = await self._get_all_active_users()
            logger.info(f"Retrieved {len(user_ids)} active users for consolidation")

        memory_types = [memory_type] if memory_type else ["semantic", "episodic"]

        result = await self._process_users_in_parallel(user_ids, memory_types)

        logger.info(
            f"Memory consolidation completed - "
            f"users_processed: {result['total_users_processed']}, "
            f"memories_scanned: {result['total_memories_scanned']}, "
            f"memories_merged: {result['total_memories_merged']}, "
            f"merge_groups: {result['total_merge_groups']}, "
            f"errors: {len(result['errors'])}"
        )

        return result

    async def _get_all_active_users(self) -> list[str]:
        user_ids = []
        async for page in iter_active_users():
            user_ids.extend(page)
        return user_ids

    async def _process_users_in_parallel(
        self,
        user_ids: list[str],
        memory_types: list[str]
    ) -> dict[str, Any]:
        stats = ConsolidationStats()
        semaphore = asyncio.Semaphore(self._max_concurrent_users)

        async def process_with_semaphore(uid: str) -> None:
            async with semaphore:
                try:
                    user_stats = await self._consolidate_user_memories(uid, memory_types)
                    stats.total_users_processed += 1
                    stats.total_memories_scanned += user_stats["memories_scanned"]
                    stats.total_memories_merged += user_stats["memories_merged"]
                    stats.total_merge_groups += user_stats["merge_groups"]
                except Exception as e:
                    logger.error(f"Failed to process user {uid}: {e}")
                    stats.errors.append(uid)

        await asyncio.gather(*[process_with_semaphore(uid) for uid in user_ids], return_exceptions=True)

        return {
            "total_users_processed": stats.total_users_processed,
            "total_memories_scanned": stats.total_memories_scanned,
            "total_memories_merged": stats.total_memories_merged,
            "total_merge_groups": stats.total_merge_groups,
            "errors": stats.errors
        }

    async def _consolidate_user_memories(
        self,
        user_id: str,
        memory_types: list[str]
    ) -> dict[str, Any]:
        memories_scanned = 0
        memories_merged = 0
        merge_groups = 0

        for memory_type in memory_types:
            type_stats = await self._consolidate_memory_type(user_id, memory_type)
            memories_scanned += type_stats["scanned"]
            memories_merged += type_stats["merged"]
            merge_groups += type_stats["groups"]

        return {
            "memories_scanned": memories_scanned,
            "memories_merged": memories_merged,
            "merge_groups": merge_groups
        }

    async def _consolidate_memory_type(
        self,
        user_id: str,
        memory_type: str
    ) -> dict[str, Any]:
        namespace = (user_id, memory_type)

        memories = self._store.list_by_namespace(namespace, return_metadata=True)

        if not memories:
            logger.info(f"No {memory_type} memories found for user {user_id}")
            return {"scanned": 0, "merged": 0, "groups": 0}

        logger.info(f"Processing {len(memories)} {memory_type} memories for user {user_id}")

        groups = self._find_similar_memory_groups(memories, user_id, memory_type)

        if groups:
            logger.info(f"Found {len(groups)} merge groups for user {user_id} ({memory_type})")

        merged_count = 0
        for group in groups:
            success = await self._merge_memory_group(group, user_id, memory_type)
            if success:
                merged_count += len(group) - 1

        return {
            "scanned": len(memories),
            "merged": merged_count,
            "groups": len(groups)
        }

    def _find_similar_memory_groups(
        self,
        memories: list[SearchItem],
        user_id: str,
        memory_type: str
    ) -> list[list[SearchItem]]:
        logger.info(f"Finding similar groups among {len(memories)} memories for user {user_id} ({memory_type})")
        processed = set()
        groups = []
        namespace = (user_id, memory_type)

        for memory in memories:
            if memory.key in processed:
                continue

            summary = memory.value.get("summary", "")
            category = memory.value.get("category")

            logger.info(f"Analyzing memory: key={memory.key}, category={category}, summary='{summary[:80]}...'")

            similar = self._store.search(
                namespace,
                query=summary,
                limit=self._search_limit
            )

            logger.info(f"Search returned {len(similar)} results for memory {memory.key}")

            candidates = []
            for result in similar:
                if result.key == memory.key:
                    logger.info(f"Skipping self-match for key {result.key}")
                    continue
                if result.key in processed:
                    logger.info(f"Skipping already processed key {result.key}")
                    continue

                # Debug logging to see similarity scores
                result_summary = result.value.get("summary", "")[:50]
                result_category = result.value.get("category")
                logger.info(
                    f"Comparing memories - Base: '{summary[:50]}...' vs "
                    f"Candidate: '{result_summary}...' - "
                    f"Score: {result.score:.4f} (threshold: {self._similarity_threshold})"
                )

                if result.score < self._similarity_threshold:
                    logger.info(f"Skipping candidate - score {result.score:.4f} below threshold {self._similarity_threshold}")
                    continue

                logger.info(f"✓ Found merge candidate - score: {result.score:.4f}, category: {result_category}")
                candidates.append(result)

            if candidates:
                group = [memory] + candidates
                groups.append(group)
                processed.add(memory.key)
                for candidate in candidates:
                    processed.add(candidate.key)
            else:
                processed.add(memory.key)

        return groups

    async def _merge_memory_group(
        self,
        memory_group: list[SearchItem],
        user_id: str,
        memory_type: str
    ) -> bool:
        if len(memory_group) < 2:
            return False

        sorted_group = sorted(memory_group, key=lambda m: m.value.get("created_at", ""))
        oldest_memory = sorted_group[0]
        newest_memory = sorted_group[-1]

        summaries = [m.value.get("summary", "") for m in sorted_group]
        categories = [m.value.get("category", "") for m in sorted_group]
        importances = [m.value.get("importance", 1) for m in sorted_group]

        llm_result = await self._generate_merged_summary(summaries, categories, importances, memory_type)
        merged_summary = llm_result["merged_summary"]
        merged_importance = llm_result["importance"]

        category_counts = Counter(categories)
        merged_category = category_counts.most_common(1)[0][0] if category_counts else categories[-1]

        newest_display = newest_memory.value.get("display_summary")
        merged_value = {
            "id": newest_memory.value.get("id") or uuid4().hex,
            "user_id": user_id,
            "type": memory_type,
            "summary": merged_summary,
            "display_summary": newest_display or merged_summary,
            "category": merged_category,
            "importance": merged_importance,
            "created_at": oldest_memory.value.get("created_at") or datetime.now(timezone.utc).isoformat(),
            "last_accessed": newest_memory.value.get("last_accessed") or datetime.now(timezone.utc).isoformat(),
            "last_used_at": newest_memory.value.get("last_used_at") or newest_memory.value.get("last_accessed") or datetime.now(timezone.utc).isoformat(),
            "tags": newest_memory.value.get("tags", []),
            "source": "memory_consolidation",
            "pinned": newest_memory.value.get("pinned", False)
        }

        namespace = (user_id, memory_type)

        try:
            self._store.put(
                namespace,
                key=newest_memory.key,
                value=merged_value,
                index=["summary"]
            )

            verification = self._store.get(namespace, newest_memory.key)
            if not verification or verification.value.get("summary") != merged_summary:
                logger.error(f"Merge verification failed for user {user_id}, key {newest_memory.key}")
                return False

            for memory in sorted_group[:-1]:
                try:
                    self._store.delete(namespace, memory.key)
                except Exception as e:
                    logger.warning(f"Failed to delete old memory {memory.key}: {e}")

            logger.info(f"Successfully merged {len(sorted_group)} memories for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to merge memory group for user {user_id}: {e}")
            return False

    async def _generate_merged_summary(
        self,
        summaries: list[str],
        categories: list[str],
        importances: list[int],
        memory_type: str
    ) -> dict[str, Any]:
        summaries_text = "\n".join([f"{i+1}. {s}" for i, s in enumerate(summaries)])
        importances_text = ", ".join([str(imp) for imp in importances])
        category_set = set(categories)
        category_text = list(category_set)[0] if len(category_set) == 1 else "Mixed"

        prompt = prompt_loader.load(
            "memory_merge_summaries",
            memory_type=memory_type,
            category=category_text,
            summaries_text=summaries_text,
            importances_text=importances_text
        )

        body_payload = {
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {
                "temperature": 0.0,
                "topP": 0.1,
                "maxTokens": 256,
                "stopSequences": []
            }
        }

        res = self._bedrock.invoke_model(
            modelId=self._llm_model_id,
            body=json.dumps(body_payload)
        )

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

        parsed = {}
        if out_text:
            try:
                parsed = json.loads(out_text)
            except Exception:
                i, j = out_text.find("{"), out_text.rfind("}")
                if i >= 0 and j > i:
                    parsed_text = out_text[i:j+1]
                    try:
                        parsed = json.loads(parsed_text)
                    except Exception:
                        logger.warning(f"Failed to parse LLM response: {out_text[:100]}")

        merged_summary = parsed.get("merged_summary", summaries[-1] if summaries else "")
        importance = parsed.get("importance", max(importances) if importances else 1)

        return {
            "merged_summary": merged_summary,
            "importance": importance
        }


memory_consolidation_service = MemoryConsolidationService()
