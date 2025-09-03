from datetime import datetime
from typing import Any, List

from pydantic import BaseModel, Field


class SourceRequest(BaseModel):
    """Request to create a source."""

    name: str
    url: str
    type: str | None = None
    category: str | None = None
    description: str | None = None


class BulkSourceRequest(BaseModel):
    """Request to create multiple sources."""

    sources: List[SourceRequest]


class Source(BaseModel):
    """Source entity for knowledge base."""

    id: str
    name: str
    url: str
    enabled: bool = True
    type: str | None = None
    category: str | None = None
    description: str | None = None
    include_path_patterns: str | None = None
    exclude_path_patterns: str | None = None
    total_max_pages: str | None = None
    recursion_depth: str | None = None


class KBSearchResult(BaseModel):
    """Knowledge base search result."""

    content: str
    source: str
    source_type: str = ""
    source_category: str = ""
    source_description: str = ""


class CrawlResult(BaseModel):
    """Result of crawling operation."""

    source_id: str
    documents_count: int
    success: bool
    message: str
    documents: List[Any] = []


class SyncResult(BaseModel):
    """Result of synchronization operation."""

    source_id: str
    success: bool
    message: str
    chunks_reindexed: int = 0
    has_changes: bool = False
    execution_time_seconds: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.now)
