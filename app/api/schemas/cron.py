from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class BackgroundSyncStartedResponse(BaseModel):
    """Response for background sync operation start."""

    job_id: str
    message: str
    started_at: str


class KbCronSyncResponse(BaseModel):
    """Response for sync-all operation."""

    success: bool
    message: str
    sources_created: int
    sources_updated: int
    sources_deleted: int
    sources_synced: List[str]
    sync_failures: List[str]
    deletion_failures: Optional[List[dict]] = None

