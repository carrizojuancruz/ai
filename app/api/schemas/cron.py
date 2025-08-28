"""Schemas for cron API endpoints."""

from typing import List

from pydantic import BaseModel

from app.knowledge.models import SyncResult


class CronSyncResponse(BaseModel):
    """Response for sync-all operation."""

    success: bool
    message: str
    results: List[SyncResult]
    total_sources: int
    successful_syncs: int
    sources_with_changes: int


class CronSyncSourceResponse(BaseModel):
    """Response for single source sync operation."""

    success: bool
    message: str
    result: SyncResult | None


class CronStatusResponse(BaseModel):
    """Response for sync system status check."""

    status: str
    message: str
