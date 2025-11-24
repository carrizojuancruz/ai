"""Unified synchronization service for all knowledge base sources."""

import logging
import time
from typing import Any, Dict

from app.core.config import config
from app.knowledge.constants import (
    VERA_GUIDANCE_CATEGORY,
    VERA_GUIDANCE_CONTENT_SOURCE,
    VERA_GUIDANCE_DESCRIPTION,
    VERA_GUIDANCE_NAME,
    VERA_GUIDANCE_TYPE,
)
from app.knowledge.models import Source
from app.knowledge.s3_sync_service import S3SyncService
from app.knowledge.service import KnowledgeService
from app.knowledge.sync_service import KnowledgeBaseSyncService
from app.knowledge.utils import generate_source_id

logger = logging.getLogger(__name__)


class UnifiedSyncService:
    """Orchestrates all knowledge base synchronization."""

    def __init__(self):
        self.external_sync = KnowledgeBaseSyncService()
        self.s3_sync = S3SyncService()
        self.kb_service = KnowledgeService()

    async def sync_all_sources(self) -> Dict[str, Any]:
        """Synchronize all knowledge base sources."""
        start_time = time.time()
        operations = []

        logger.info("Starting unified sync")

        for sync_fn, op_type in [
            (self._sync_s3, "s3"),
            (self._sync_guidance, "guidance"),
            (self._sync_external, "external")
        ]:
            try:
                result = await sync_fn()
                operations.append(result)
            except Exception as e:
                logger.error(f"{op_type} sync failed: {e}", exc_info=True)
                operations.append({
                    "success": False,
                    "operation_type": op_type,
                    "error": str(e)
                })

        summary = self._calculate_summary(operations)
        success = all(op.get("success", False) for op in operations)

        logger.info(
            f"Unified sync completed in {time.time() - start_time:.2f}s: "
            f"{summary['sources_synced']} sources, {summary['chunks_created']} chunks"
        )

        return {
            "success": success,
            "total_time_seconds": round(time.time() - start_time, 2),
            "operations": operations,
            "summary": summary
        }

    async def _sync_external(self) -> Dict[str, Any]:
        """Sync external sources from FOS API."""
        result = await self.external_sync.sync_all(limit=None)

        return {
            "success": result.get("success", True),
            "operation_type": "external",
            "sources_synced": result.get("sources_created", 0) + result.get("sources_updated", 0),
            "chunks_created": result.get("total_chunks_created", 0),
            "errors": result.get("sources_errors", 0)
        }

    async def _sync_s3(self) -> Dict[str, Any]:
        """Sync S3 files to vector store."""
        result = await self.s3_sync.sync_all(prefix="")

        chunks = sum(
            d.get("chunk_count", 0)
            for d in result.get("details", [])
            if d.get("success", False)
        )

        return {
            "success": result.get("success", True),
            "operation_type": "s3",
            "sources_synced": result.get("succeeded", 0),
            "chunks_created": chunks,
            "errors": result.get("failed", 0)
        }

    async def _sync_guidance(self) -> Dict[str, Any]:
        """Sync Vera guidance documentation."""
        if not config.VERA_GUIDANCE_URL:
            logger.warning("VERA_GUIDANCE_URL not configured")
            return {
                "success": False,
                "operation_type": "guidance",
                "sources_synced": 0,
                "chunks_created": 0,
                "errors": 1
            }

        source = Source(
            id=generate_source_id(config.VERA_GUIDANCE_URL),
            name=VERA_GUIDANCE_NAME,
            url=config.VERA_GUIDANCE_URL,
            enabled=True,
            type=VERA_GUIDANCE_TYPE,
            category=VERA_GUIDANCE_CATEGORY,
            description=VERA_GUIDANCE_DESCRIPTION,
            recursion_depth=config.VERA_GUIDANCE_RECURSION_DEPTH
        )

        result = await self.kb_service.upsert_source(source, content_source=VERA_GUIDANCE_CONTENT_SOURCE)

        return {
            "success": result.get("success", True),
            "operation_type": "guidance",
            "sources_synced": 1,
            "chunks_created": result.get("documents_added", 0),
            "errors": 0 if result.get("success") else 1
        }

    def _calculate_summary(self, operations: list[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate aggregate statistics."""
        return {
            "sources_synced": sum(op.get("sources_synced", 0) for op in operations),
            "chunks_created": sum(op.get("chunks_created", 0) for op in operations),
            "errors": sum(op.get("errors", 0) for op in operations)
        }
