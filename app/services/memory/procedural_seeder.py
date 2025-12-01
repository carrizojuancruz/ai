"""Procedural memory seeder for supervisor routing examples and finance templates.

Always syncs S3 to match JSONL files exactly (creates new, updates changed, deletes orphans).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from app.services.memory.store_factory import create_s3_vectors_store_from_env

logger = logging.getLogger(__name__)

SUPERVISOR_PROCEDURAL_NAMESPACE = ("system", "supervisor_procedural")
SUPERVISOR_PROCEDURAL_INDEX_FIELDS = ["summary"]

FINANCE_PROCEDURAL_NAMESPACE = ("system", "finance_procedural_templates")
FINANCE_PROCEDURAL_INDEX_FIELDS = ["name", "description", "tags"]


@dataclass
class SupervisorProcedural:
    """Supervisor routing procedural memory structure."""

    key: str
    summary: str
    category: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SupervisorProcedural | None:
        """Create from dictionary, return None if invalid."""
        if not data.get("key"):
            return None
        return cls(
            key=data["key"],
            summary=data.get("summary", ""),
            category=data.get("category", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "key": self.key,
            "summary": self.summary,
            "category": self.category,
        }

    def has_changed(self, other: dict[str, Any]) -> bool:
        """Check if this procedural differs from stored version."""
        return (
            self.summary != other.get("summary")
            or self.category != other.get("category")
        )


@dataclass
class FinanceProcedural:
    """Finance procedural template structure."""

    id: str
    name: str
    description: str
    tags: list[str]
    sql_hint: str
    examples: list[str]
    version: str
    deprecated: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FinanceProcedural | None:
        """Create from dictionary, return None if invalid."""
        if not data.get("id"):
            return None
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            tags=data.get("tags", []),
            sql_hint=data.get("sql_hint", ""),
            examples=data.get("examples", []),
            version=data.get("version", "1.0"),
            deprecated=data.get("deprecated", False),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "sql_hint": self.sql_hint,
            "examples": self.examples,
            "version": self.version,
            "deprecated": self.deprecated,
        }

    def has_changed(self, other: dict[str, Any]) -> bool:
        """Check if this template differs from stored version."""
        return (
            self.name != other.get("name")
            or self.description != other.get("description")
            or self.sql_hint != other.get("sql_hint")
            or self.tags != other.get("tags", [])
            or self.examples != other.get("examples", [])
            or self.version != other.get("version")
            or self.deprecated != other.get("deprecated")
        )


@dataclass
class SyncResult:
    """Result of a sync operation with detailed breakdown."""

    ok: bool = True
    error: Optional[str] = None
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)  # (key, error_message)

    @property
    def total_items(self) -> int:
        """Total number of items encountered (successful + failed)."""
        return len(self.created) + len(self.updated) + len(self.deleted) + len(self.skipped) + len(self.failed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "error": self.error,
            "created": self.created,
            "updated": self.updated,
            "deleted": self.deleted,
            "skipped": self.skipped,
            "failed": [{
                "key": key,
                "error": error
            } for key, error in self.failed],
            "summary": {
                "created": len(self.created),
                "updated": len(self.updated),
                "deleted": len(self.deleted),
                "skipped": len(self.skipped),
                "failed": len(self.failed),
                "total": self.total_items,
            },
        }


class ProceduralMemorySeeder:
    """Syncs procedural memories from JSONL files to S3 on startup."""

    def __init__(self, base_path: Optional[Path] = None):
        if base_path is None:
            base_path = Path(__file__).resolve().parents[3]
        self.base_path = base_path
        self.procedural_files = [
            "app/scripts/procedural memory examples/supervisor_routing_examples.jsonl",
            "app/scripts/procedural memory examples/supervisor_routing_goal_financial_examples.jsonl",
        ]
        self.finance_template_file = "app/scripts/procedural memory examples/finance_procedural_templates.jsonl"

    async def seed_supervisor_procedurals(self) -> SyncResult:
        """Sync supervisor procedural memories: S3 = JSONL."""
        logger.info("Syncing supervisor procedural memories")
        result = SyncResult()

        try:
            store = create_s3_vectors_store_from_env()
        except Exception as e:
            logger.error("Failed to create S3 vectors store: %s", e)
            return SyncResult(ok=False, error=str(e))

        # Get existing from S3
        existing: dict[str, dict] = {}
        try:
            items = store.list_by_namespace(SUPERVISOR_PROCEDURAL_NAMESPACE, return_metadata=True, max_results=1000)
            existing = {item.key: item.value for item in items}
        except Exception as e:
            logger.warning("Failed to list existing procedurals: %s", e)

        json_items: dict[str, SupervisorProcedural] = {}
        for jsonl_path in self.procedural_files:
            file_path = self.base_path / jsonl_path
            if not file_path.exists():
                continue
            with file_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        procedural = SupervisorProcedural.from_dict(data)
                        if procedural:
                            json_items[procedural.key] = procedural
                    except json.JSONDecodeError:
                        continue

        for key, procedural in json_items.items():
            try:
                if key not in existing:
                    store.put(SUPERVISOR_PROCEDURAL_NAMESPACE, key, procedural.to_dict(), index=SUPERVISOR_PROCEDURAL_INDEX_FIELDS)
                    result.created.append(key)
                elif procedural.has_changed(existing[key]):
                    store.put(SUPERVISOR_PROCEDURAL_NAMESPACE, key, procedural.to_dict(), index=SUPERVISOR_PROCEDURAL_INDEX_FIELDS)
                    result.updated.append(key)
                else:
                    result.skipped.append(key)
            except Exception as e:
                logger.error("Failed to sync supervisor procedural '%s': %s", key, e)
                result.failed.append((key, str(e)))

        for key in existing:
            if key not in json_items:
                try:
                    store.delete(SUPERVISOR_PROCEDURAL_NAMESPACE, key)
                    result.deleted.append(key)
                except Exception as e:
                    logger.error("Failed to delete supervisor procedural '%s': %s", key, e)
                    result.failed.append((key, str(e)))

        summary = result.to_dict()["summary"]
        logger.info(
            "Supervisor procedurals synced: created=%d updated=%d deleted=%d skipped=%d failed=%d total=%d",
            summary["created"], summary["updated"], summary["deleted"], summary["skipped"], summary["failed"], summary["total"]
        )
        return result

    async def seed_finance_templates(self) -> SyncResult:
        """Sync finance templates: S3 = JSONL."""
        logger.info("Syncing finance procedural templates")
        result = SyncResult()

        try:
            store = create_s3_vectors_store_from_env()
        except Exception as e:
            logger.error("Failed to create S3 vectors store: %s", e)
            return SyncResult(ok=False, error=str(e))

        file_path = self.base_path / self.finance_template_file
        if not file_path.exists():
            return SyncResult(ok=False, error="file_not_found")

        # Get existing from S3
        existing: dict[str, dict] = {}
        try:
            items = store.list_by_namespace(FINANCE_PROCEDURAL_NAMESPACE, return_metadata=True, max_results=1000)
            existing = {item.key: item.value for item in items}
        except Exception as e:
            logger.warning("Failed to list existing finance templates: %s", e)

        # Load from JSONL
        json_items: dict[str, FinanceProcedural] = {}
        with file_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    procedural = FinanceProcedural.from_dict(data)
                    if procedural:
                        json_items[procedural.id] = procedural
                except json.JSONDecodeError:
                    continue

        for key, procedural in json_items.items():
            try:
                if key not in existing:
                    store.put(FINANCE_PROCEDURAL_NAMESPACE, key, procedural.to_dict(), index=FINANCE_PROCEDURAL_INDEX_FIELDS)
                    result.created.append(key)
                elif procedural.has_changed(existing[key]):
                    store.put(FINANCE_PROCEDURAL_NAMESPACE, key, procedural.to_dict(), index=FINANCE_PROCEDURAL_INDEX_FIELDS)
                    result.updated.append(key)
                else:
                    result.skipped.append(key)
            except Exception as e:
                logger.error("Failed to sync finance procedural '%s': %s", key, e)
                result.failed.append((key, str(e)))

        for key in existing:
            if key not in json_items:
                try:
                    store.delete(FINANCE_PROCEDURAL_NAMESPACE, key)
                    result.deleted.append(key)
                except Exception as e:
                    logger.error("Failed to delete finance procedural '%s': %s", key, e)
                    result.failed.append((key, str(e)))

        summary = result.to_dict()["summary"]
        logger.info(
            "Finance procedurals synced: created=%d updated=%d deleted=%d skipped=%d failed=%d total=%d",
            summary["created"], summary["updated"], summary["deleted"], summary["skipped"], summary["failed"], summary["total"]
        )
        return result

    async def verify_procedurals_exist(self) -> dict[str, Any]:
        """Check supervisor procedural count in S3."""
        try:
            store = create_s3_vectors_store_from_env()
            results = store.list_by_namespace(SUPERVISOR_PROCEDURAL_NAMESPACE, return_metadata=True, max_results=1000)
            count = len(results) if results else 0
            return {"ok": True, "count": count, "sample_keys": [r.key for r in (results or [])[:5]]}
        except Exception as e:
            return {"ok": False, "error": str(e), "count": 0, "sample_keys": []}


_seeder: Optional[ProceduralMemorySeeder] = None


def get_procedural_seeder() -> ProceduralMemorySeeder:
    global _seeder
    if _seeder is None:
        _seeder = ProceduralMemorySeeder()
    return _seeder
