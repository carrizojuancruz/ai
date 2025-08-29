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

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["message"])

        return KbCronSyncResponse(
            success=True,
            message="External sync completed successfully",
            sources_created=result["sources_created"],
            sources_updated=result["sources_updated"],
            sources_deleted=result["sources_deleted"],
            sources_synced=result["sources_synced"],
            sync_failures=result["sync_failures"]
        )
    except Exception as e:
        logger.error(f"Failed to sync all sources: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Sync operation failed: {str(e)}"
        ) from e
