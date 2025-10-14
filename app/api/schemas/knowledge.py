from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str
    filter: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional metadata filter for search results",
        examples=[
            {"content_source": "internal"},
            {"content_source": "external"},
            {"file_type": "markdown"}
        ]
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "query": "How do I connect my bank?",
                    "filter": {"content_source": "internal"}
                },
                {
                    "query": "Investment strategies",
                    "filter": {"content_source": "external"}
                }
            ]
        }

class SearchResponse(BaseModel):
    results: list
    query: str
    total_results: int


class SourceResponse(BaseModel):
    """Response model for source data."""

    id: str
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


class DeleteAllVectorsResponse(BaseModel):
    """Response model for delete all vectors operation."""

    success: bool
    vectors_deleted: int
    message: str
    vectors_failed: Optional[int] = None
    error: Optional[str] = None
