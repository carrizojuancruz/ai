from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


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


class MemoryMergeResponse(BaseModel):
    """Response for memory consolidation operation."""

    ok: bool
    total_users_processed: int
    total_memories_scanned: int
    total_memories_merged: int
    total_merge_groups: int
    duration_seconds: float
    errors: List[str] = Field(default_factory=list)


