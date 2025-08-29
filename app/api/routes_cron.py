from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas.cron import KbCronSyncResponse
from app.knowledge.orchestrator import KnowledgeBaseOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cron", tags=["Cron"])


@router.post("/knowledge-base", response_model=KbCronSyncResponse)
async def sync_all_sources() -> KbCronSyncResponse:
    """Trigger synchronization of all knowledge base sources."""
    try:
        orchestrator = KnowledgeBaseOrchestrator()
        result = await orchestrator.sync_all()

        return KbCronSyncResponse(
            success=result["success"],
            message=result.get("message", "Sync operation completed"),
            sources_created=result.get("sources_created", 0),
            sources_updated=result.get("sources_updated", 0),
            sources_deleted=result.get("sources_deleted", 0),
            sources_synced=result.get("sources_synced", []),
            sync_failures=result.get("sync_failures", []),
            deletion_failures=result.get("deletion_failures")
        )
    except Exception as e:
        logger.error(f"Failed to sync all sources: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Sync operation failed: {str(e)}"
        ) from e
