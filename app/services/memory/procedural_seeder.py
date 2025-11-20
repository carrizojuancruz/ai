"""Procedural memory seeder for supervisor routing examples and finance templates.

This module handles automatic loading of supervisor procedural memories
(routing examples) and finance procedural templates from JSONL files into
the LangGraph S3 Vectors store during application startup.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from app.services.memory.store_factory import create_s3_vectors_store_from_env

logger = logging.getLogger(__name__)

SUPERVISOR_PROCEDURAL_NAMESPACE = ("system", "supervisor_procedural")
SUPERVISOR_PROCEDURAL_INDEX_FIELDS = ["summary"]

FINANCE_PROCEDURAL_NAMESPACE = ("system", "finance_procedural_templates")
FINANCE_PROCEDURAL_INDEX_FIELDS = ["name", "description", "tags"]


class ProceduralMemorySeeder:
    """Service for seeding supervisor procedural memories and finance templates on startup."""

    def __init__(self, base_path: Optional[Path] = None):
        """Initialize the seeder.

        Args:
            base_path: Base directory for JSONL files. Defaults to project root.

        """
        if base_path is None:
            base_path = Path(__file__).resolve().parents[3]
        self.base_path = base_path
        self.procedural_files = [
            "app/scripts/procedural memory examples/supervisor_routing_examples.jsonl",
            "app/scripts/procedural memory examples/supervisor_routing_goal_financial_examples.jsonl",
        ]
        self.finance_template_file = "app/scripts/procedural memory examples/finance_procedural_templates.jsonl"

    async def seed_supervisor_procedurals(self, force: bool = False) -> dict[str, Any]:
        """Seed supervisor procedural memories from JSONL files.

        Args:
            force: If True, overwrite existing items. If False, skip existing items.

        Returns:
            Dictionary with seeding statistics:
            {
                "ok": bool,
                "total_files": int,
                "total_processed": int,
                "created": int,
                "skipped": int,
                "errors": int,
                "files": [{"file": str, "created": int, "skipped": int, "errors": int}]
            }

        """
        logger.info("Starting supervisor procedural memory seeding (force=%s)", force)

        try:
            store = create_s3_vectors_store_from_env()
        except Exception as e:
            logger.error("Failed to create S3 vectors store: %s", e)
            return {
                "ok": False,
                "error": "store_creation_failed",
                "message": str(e),
                "total_files": 0,
                "total_processed": 0,
                "created": 0,
                "skipped": 0,
                "errors": 0,
            }

        existing_keys: set[str] | None = None
        if not force:
            try:
                existing_items = store.list_by_namespace(
                    SUPERVISOR_PROCEDURAL_NAMESPACE,
                    return_metadata=True,
                    max_results=1000,
                    limit=None,
                )
                existing_keys = {item.key for item in existing_items}
                logger.debug("Found %d existing supervisor procedurals", len(existing_keys))
            except Exception as e:
                logger.warning("Failed to list existing procedurals, will check individually: %s", e)

        total_created = 0
        total_skipped = 0
        total_errors = 0
        total_processed = 0
        file_stats = []

        for jsonl_file_path in self.procedural_files:
            file_path = self.base_path / jsonl_file_path
            stats = await self._seed_file(store, file_path, force, existing_keys)

            file_stats.append({
                "file": jsonl_file_path,
                "created": stats["created"],
                "skipped": stats["skipped"],
                "errors": stats["errors"],
            })

            total_created += stats["created"]
            total_skipped += stats["skipped"]
            total_errors += stats["errors"]
            total_processed += stats["processed"]

        result = {
            "ok": True,
            "total_files": len(self.procedural_files),
            "total_processed": total_processed,
            "created": total_created,
            "skipped": total_skipped,
            "errors": total_errors,
            "files": file_stats,
        }

        logger.info(
            "Supervisor procedural seeding completed: processed=%d created=%d skipped=%d errors=%d",
            total_processed,
            total_created,
            total_skipped,
            total_errors,
        )

        return result

    async def _seed_file(self, store: Any, file_path: Path, force: bool, existing_keys: set[str] | None = None) -> dict[str, int]:
        """Seed supervisor procedural memories from a single JSONL file.

        Args:
            store: S3 vectors store instance
            file_path: Path to JSONL file
            force: Whether to overwrite existing items
            existing_keys: Pre-fetched set of existing keys (None if force=True, otherwise set of existing keys)

        Returns:
            Dictionary with stats: {"processed": int, "created": int, "skipped": int, "errors": int}

        """
        if not file_path.exists():
            logger.warning("Procedural file not found: %s", file_path)
            return {"processed": 0, "created": 0, "skipped": 0, "errors": 1}

        if existing_keys is None:
            existing_keys = set()

        created = 0
        skipped = 0
        errors = 0
        processed = 0

        logger.info("Processing procedural file: %s", file_path.name)

        try:
            with file_path.open("r", encoding="utf-8") as f:
                for line_num, raw_line in enumerate(f, 1):
                    line = raw_line.strip()
                    if not line:
                        continue

                    processed += 1

                    try:
                        item_data = json.loads(line)
                    except json.JSONDecodeError as e:
                        logger.warning("Failed to parse line %d in %s: %s", line_num, file_path.name, e)
                        errors += 1
                        continue

                    item_key = item_data.get("key")
                    if not item_key:
                        logger.warning("Item on line %d in %s missing 'key'; skipping", line_num, file_path.name)
                        errors += 1
                        continue

                    # Check if exists using pre-fetched set
                    if not force and existing_keys and item_key in existing_keys:
                        logger.debug("Procedural '%s' already exists; skipping", item_key)
                        skipped += 1
                        continue

                    try:
                        store.put(
                            SUPERVISOR_PROCEDURAL_NAMESPACE,
                            item_key,
                            item_data,
                            index=SUPERVISOR_PROCEDURAL_INDEX_FIELDS,
                        )

                        action = "updated" if (existing_keys and item_key in existing_keys) else "created"
                        logger.debug("Procedural '%s' %s", item_key, action)
                        created += 1

                    except Exception as e:
                        logger.error("Failed to store procedural '%s': %s", item_key, e)
                        errors += 1

        except Exception as e:
            logger.error("Error processing file %s: %s", file_path, e)
            errors += 1

        logger.info(
            "File %s: processed=%d created=%d skipped=%d errors=%d",
            file_path.name,
            processed,
            created,
            skipped,
            errors,
        )

        return {"processed": processed, "created": created, "skipped": skipped, "errors": errors}

    async def seed_finance_templates(self, force: bool = False) -> dict[str, Any]:
        """Seed finance procedural templates from JSONL file.

        Args:
            force: If True, overwrite existing items. If False, skip existing items.

        Returns:
            Dictionary with seeding statistics:
            {
                "ok": bool,
                "total_processed": int,
                "created": int,
                "skipped": int,
                "errors": int,
            }

        """
        logger.info("Starting finance procedural template seeding (force=%s)", force)

        try:
            store = create_s3_vectors_store_from_env()
        except Exception as e:
            logger.error("Failed to create S3 vectors store: %s", e)
            return {
                "ok": False,
                "error": "store_creation_failed",
                "message": str(e),
                "total_processed": 0,
                "created": 0,
                "skipped": 0,
                "errors": 0,
            }

        file_path = self.base_path / self.finance_template_file
        if not file_path.exists():
            logger.warning("Finance template file not found: %s", file_path)
            return {
                "ok": False,
                "error": "file_not_found",
                "message": f"Finance template file not found: {file_path}",
                "total_processed": 0,
                "created": 0,
                "skipped": 0,
                "errors": 0,
            }

        existing_keys: set[str] = set()
        if not force:
            try:
                existing_items = store.list_by_namespace(
                    FINANCE_PROCEDURAL_NAMESPACE,
                    return_metadata=True,
                    max_results=1000,
                    limit=None,
                )
                existing_keys = {item.key for item in existing_items}
                logger.debug("Found %d existing finance templates", len(existing_keys))
            except Exception as e:
                logger.warning("Failed to list existing finance templates, will check individually: %s", e)

        created = 0
        skipped = 0
        errors = 0
        processed = 0

        logger.info("Processing finance template file: %s", file_path.name)

        try:
            with file_path.open("r", encoding="utf-8") as f:
                for line_num, raw_line in enumerate(f, 1):
                    line = raw_line.strip()
                    if not line:
                        continue

                    processed += 1

                    try:
                        template_data = json.loads(line)
                    except json.JSONDecodeError as e:
                        logger.warning("Failed to parse line %d in %s: %s", line_num, file_path.name, e)
                        errors += 1
                        continue

                    template_id = template_data.get("id")
                    if not template_id:
                        logger.warning("Template on line %d in %s missing 'id'; skipping", line_num, file_path.name)
                        errors += 1
                        continue

                    # Check if exists using pre-fetched set
                    if not force and template_id in existing_keys:
                        logger.debug("Finance template '%s' already exists; skipping", template_id)
                        skipped += 1
                        continue

                    try:
                        store.put(
                            FINANCE_PROCEDURAL_NAMESPACE,
                            template_id,
                            template_data,
                            index=FINANCE_PROCEDURAL_INDEX_FIELDS,
                        )

                        action = "updated" if template_id in existing_keys else "created"
                        logger.debug("Finance template '%s' %s", template_id, action)
                        created += 1

                    except Exception as e:
                        logger.error("Failed to store finance template '%s': %s", template_id, e)
                        errors += 1

        except Exception as e:
            logger.error("Error processing finance template file %s: %s", file_path, e)
            errors += 1

        logger.info(
            "Finance template seeding completed: processed=%d created=%d skipped=%d errors=%d",
            processed,
            created,
            skipped,
            errors,
        )

        return {
            "ok": True,
            "total_processed": processed,
            "created": created,
            "skipped": skipped,
            "errors": errors,
        }

    async def verify_procedurals_exist(self) -> dict[str, Any]:
        """Verify that supervisor procedural memories exist in the store.

        Uses list_by_namespace() with pagination to get accurate counts,
        bypassing the semantic search limit of 100 results.

        Returns:
            Dictionary with verification results:
            {
                "ok": bool,
                "count": int,
                "sample_keys": list[str]  # First 5 keys
            }

        """
        try:
            store = create_s3_vectors_store_from_env()
            results = store.list_by_namespace(
                SUPERVISOR_PROCEDURAL_NAMESPACE,
                return_metadata=True,
                max_results=1000,
                limit=None,
            )

            count = len(results) if results else 0
            sample_keys = [getattr(r, "key", None) for r in (results or [])[:5]]

            logger.info("Verification: Found %d supervisor procedural memories", count)

            return {
                "ok": True,
                "count": count,
                "sample_keys": sample_keys,
            }

        except Exception as e:
            logger.error("Failed to verify procedural memories: %s", e)
            return {
                "ok": False,
                "error": str(e),
                "count": 0,
                "sample_keys": [],
            }


# Global instance
_seeder: Optional[ProceduralMemorySeeder] = None


def get_procedural_seeder() -> ProceduralMemorySeeder:
    """Get the global procedural memory seeder instance."""
    global _seeder
    if _seeder is None:
        _seeder = ProceduralMemorySeeder()
    return _seeder
