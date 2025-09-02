from __future__ import annotations

import logging
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.api.schemas.cron import BackgroundSyncStartedResponse
from app.knowledge.orchestrator import KnowledgeBaseOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cron", tags=["Cron"])


@router.post("/knowledge-base", response_model=BackgroundSyncStartedResponse)
async def sync_all_sources(background_tasks: BackgroundTasks) -> BackgroundSyncStartedResponse:
    """Trigger synchronization of all knowledge base sources in background."""
    try:
        job_id = str(uuid4())
        started_at = datetime.utcnow().isoformat()

        orchestrator = KnowledgeBaseOrchestrator()
        background_tasks.add_task(orchestrator.run_background_sync, job_id)

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
