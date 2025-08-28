"""Schemas for cron API endpoints."""

from pydantic import BaseModel


class CronSyncResponse(BaseModel):
    """Response for sync-all operation."""

    success: bool
    message: str
    sources_created: int
    sources_updated: int
    sources_deleted: int
    kb_synced: int
    kb_failed: int

class CronStatusResponse(BaseModel):
    """Response for sync system status check."""

    status: str
    message: str
