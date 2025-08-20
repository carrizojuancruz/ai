from typing import Any, Dict, List

from pydantic import BaseModel, Field


class SourceRequest(BaseModel):
    """Request to create a source."""

    name: str
    url: str


class BulkSourceRequest(BaseModel):
    """Request to create multiple sources."""

    sources: List[SourceRequest]


class Source(BaseModel):
    """Source entity for knowledge base."""

    id: str
    name: str
    url: str
    enabled: bool = True


class KBSearchResult(BaseModel):
    """Knowledge base search result."""

    text: str
    source: str
    score: float | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CrawlResult(BaseModel):
    """Result of crawling operation."""

    source_id: str
    documents_count: int
    success: bool
    message: str
    documents: List[Any] = []
