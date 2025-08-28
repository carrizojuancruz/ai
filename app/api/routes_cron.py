from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas.cron import CronStatusResponse, CronSyncResponse
from app.knowledge.management.sync_manager import SyncManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cron", tags=["Cron"])


@router.post("/knowledge-base/sync-all", response_model=CronSyncResponse)
async def sync_all_sources() -> CronSyncResponse:
    """Trigger synchronization of all knowledge base sources."""
    try:
        sync_manager = SyncManager()
        results = await sync_manager.sync_all()
        successful_syncs = sum(1 for r in results if r.success)
        sources_with_changes = sum(1 for r in results if r.has_changes)
        return CronSyncResponse(
            success=True,
            message=f"Sync completed: {successful_syncs}/{len(results)} successful",
            results=results,
            total_sources=len(results),
            successful_syncs=successful_syncs,
            sources_with_changes=sources_with_changes
        )
    except Exception as e:
        logger.error(f"Failed to sync all sources: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Sync operation failed: {str(e)}"
        ) from e

@router.get("/knowledge-base/status", response_model=CronStatusResponse)
async def get_sync_status() -> CronStatusResponse:
    """Get the current status of the knowledge base sync system."""
    try:
        return CronStatusResponse(
            status="active",
            message="Knowledge base sync system is operational"
        )
    except Exception as e:
        logger.error(f"Failed to get sync status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Status check failed: {str(e)}"
        ) from e
