from pydantic import BaseModel


class KbCronSyncResponse(BaseModel):
    """Response for sync-all operation."""

    success: bool
    message: str
    sources_created: int
    sources_updated: int
    sources_deleted: int
    sources_synced: int
    sync_failures: int

