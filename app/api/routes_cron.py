from __future__ import annotations

import logging
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.api.schemas.cron import BackgroundSyncStartedResponse
from app.knowledge.sync_service import KnowledgeBaseSyncService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cron", tags=["Cron"])


@router.post("/knowledge-base", response_model=BackgroundSyncStartedResponse)
async def sync_all_sources(background_tasks: BackgroundTasks) -> BackgroundSyncStartedResponse:
    """Trigger synchronization of all knowledge base sources in background."""
    try:
        job_id = str(uuid4())
        started_at = datetime.utcnow().isoformat()

        background_tasks.add_task(run_background_sync, job_id)

        return BackgroundSyncStartedResponse(
            job_id=job_id,
            message="Knowledge base sync started in background",
            started_at=started_at
        )
    except Exception as e:
        logger.error(f"Failed to start background sync: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start sync operation: {str(e)}"
        ) from e


async def run_background_sync(job_id: str):
    start_time = datetime.utcnow()

    try:
        logger.info(f"Starting knowledge sync job {job_id}")

        sync_service = KnowledgeBaseSyncService()
        result = await sync_service.sync_all()
        duration = (datetime.utcnow() - start_time).total_seconds()

        sync_failures = result.get('sync_failures', [])
        deletion_failures = result.get('deletion_failures', [])
        sync_failure_info = [f"{url}: sync failed" for url in sync_failures] if sync_failures else []
        deletion_failure_info = [f"{fail['url']}: {fail['message']}" for fail in deletion_failures] if deletion_failures else []
        all_failures = sync_failure_info + deletion_failure_info

        logger.info(
            f"Job {job_id} completed successfully in {duration:.2f}s: "
            f"Created: {result.get('sources_created', 0)}, "
            f"Updated: {result.get('sources_updated', 0)}, "
            f"Deleted: {result.get('sources_deleted', 0)}, "
            f"Synced: {result.get('sources_synced', [])}, "
            f"Failures: {all_failures}"
        )

    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.error(f"Job {job_id} failed after {duration:.2f}s: {str(e)}")
        raise e
