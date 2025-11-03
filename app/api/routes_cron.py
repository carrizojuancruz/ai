from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.api.schemas.cron import BackgroundSyncStartedResponse
from app.knowledge.sync_service import KnowledgeBaseSyncService
from app.services.goals import get_goals_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cron", tags=["Cron"])


@router.post("/knowledge-base", response_model=BackgroundSyncStartedResponse)
async def sync_all_sources(
    background_tasks: BackgroundTasks,
    limit: Optional[int] = None
) -> BackgroundSyncStartedResponse:
    """Trigger synchronization of all knowledge base sources in background.

    Args:
        background_tasks: FastAPI background tasks handler.
        limit: Optional limit on the number of sources to sync. If not provided, all enabled sources will be synced.

    """
    try:
        job_id = str(uuid4())
        started_at = datetime.utcnow().isoformat()

        logger.info(f"Starting background sync with job_id={job_id}")

        background_tasks.add_task(run_background_sync_non_async, job_id, limit)

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


def run_background_sync_non_async(job_id: str, limit: Optional[int] = None):
    """Non-async sync wrapper - runs in separate thread (StackOverflow solution)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(run_background_sync(job_id, limit))
    finally:
        loop.close()


async def run_background_sync(job_id: str, limit: Optional[int] = None):
    start_time = datetime.utcnow()

    try:
        logger.info(f"Starting knowledge sync job {job_id}")

        sync_service = KnowledgeBaseSyncService()
        result = await sync_service.sync_all(limit=limit)
        duration = (datetime.utcnow() - start_time).total_seconds()

        logger.info(
            f"Job {job_id} completed successfully in {duration:.2f}s: "
            f"Created: {result.get('sources_created', 0)}, "
            f"Updated: {result.get('sources_updated', 0)}, "
            f"No changes: {result.get('sources_no_changes', 0)}, "
            f"Deleted: {result.get('sources_deleted', 0)}, "
            f"Errors: {result.get('sources_errors', 0)}, "
            f"Total chunks: {result.get('total_chunks_created', 0)}"
        )

    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.error(f"Job {job_id} failed after {duration:.2f}s: {str(e)}")
        raise e


@router.post("/goals-nudges")
async def check_goals_nudges(days_ahead: int = 7) -> dict:
    """Check all goals and trigger nudges for those that need it.

    This endpoint should be called periodically (e.g., daily) to check
    all goals and trigger notifications for:
    - Completed goals with end dates
    - Goals with high progress (>=75%)
    - Pending goals
    - Goals with deadline approaching

    Args:
        days_ahead: How many days ahead to check for deadlines (default: 7)

    """
    try:
        logger.info(f"Starting goals nudge check (days_ahead={days_ahead})")

        goals_service = get_goals_service()
        result = await goals_service.check_all_goals_for_nudges(days_ahead)

        logger.info(
            f"Goals nudge check complete: total={result['total']}, "
            f"triggered={result['triggered']}, skipped={result['skipped']}"
        )

        return {
            "status": "success",
            "message": f"Checked {result['total']} goals",
            "triggered": result['triggered'],
            "skipped": result['skipped'],
        }

    except Exception as e:
        logger.error(f"Goals nudge check failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check goals: {str(e)}"
        ) from e
