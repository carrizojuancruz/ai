from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str

class SearchResponse(BaseModel):
    results: list
    query: str
    total_results: int


class SourceResponse(BaseModel):
    """Response model for source data."""

    name: str
    url: str
    type: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    include_path_patterns: Optional[str] = None
    exclude_path_patterns: Optional[str] = None
    total_max_pages: Optional[str] = None
    recursion_depth: Optional[str] = None
    last_sync: Optional[datetime] = None


class SourcesResponse(BaseModel):
    """Response model for sources list."""

    sources: list[SourceResponse]
    total_sources: int
