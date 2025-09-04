from datetime import datetime
from typing import List, Optional

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
    total_max_pages: Optional[int] = None
    recursion_depth: Optional[int] = None
    last_sync: Optional[datetime] = None
    section_urls: Optional[List[str]] = None


class SourcesResponse(BaseModel):
    """Response model for sources list."""

    sources: list[SourceResponse]
    total_sources: int


class ChunkData(BaseModel):
    """Simple chunk data with just section_url and content."""

    section_url: str
    content: str


class SourceDetailsResponse(BaseModel):
    """Detailed response model for a single source with chunk information."""

    source: SourceResponse
    total_chunks: int
    chunks: list[ChunkData]
