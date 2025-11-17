from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SearchRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
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
    )

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

class SourceDetailsResponse(BaseModel):
    """Detailed response model for a single source with chunk information."""

    source: SourceResponse
    total_chunks: int
    chunks: list[dict]


class DeleteAllVectorsResponse(BaseModel):
    """Response model for delete all vectors operation."""

    success: bool
    vectors_deleted: int
    message: str
    vectors_failed: Optional[int] = None
    error: Optional[str] = None


class SyncSourceRequest(BaseModel):
    """Request schema for syncing a single source."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "url": "https://docs.python.org/3/",
                "name": "Python 3 Documentation",
                "type": "Documentation",
                "category": "Programming",
                "description": "Official Python 3 documentation",
                "total_max_pages": 100,
                "recursion_depth": 3,
                "force_reindex": False
            }
        }
    )

    url: str = Field(..., description="Source URL to synchronize")
    name: Optional[str] = Field(None, description="Display name for the source")
    type: Optional[str] = Field("External", description="Source type")
    category: Optional[str] = Field("General", description="Source category")
    description: Optional[str] = Field("", description="Source description")
    include_path_patterns: Optional[str] = Field(None, description="Regex pattern for paths to include")
    exclude_path_patterns: Optional[str] = Field(None, description="Regex pattern for paths to exclude")
    total_max_pages: Optional[int] = Field(20, ge=1, le=1000, description="Maximum pages to crawl")
    recursion_depth: Optional[int] = Field(2, ge=0, le=10, description="Maximum crawl depth")
    force_reindex: bool = Field(False, description="Force reindex even if no changes detected")


class SyncSourceResponse(BaseModel):
    """Response schema for source sync operation."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "source_url": "https://docs.python.org/3/",
                "source_id": "a1b2c3d4e5f6g7h8",
                "is_new_source": True,
                "documents_processed": 50,
                "documents_added": 250,
                "processing_time_seconds": 120.5,
                "message": "Successfully synchronized source",
                "crawl_type": "recursive",
                "error": None,
                "crawl_error": None
            }
        }
    )

    success: bool
    source_url: str
    source_id: str
    is_new_source: bool
    documents_processed: int
    documents_added: int
    processing_time_seconds: float
    message: str
    crawl_type: str
    content_changed: bool
    error: Optional[str] = None
    crawl_error: Optional[str] = None



