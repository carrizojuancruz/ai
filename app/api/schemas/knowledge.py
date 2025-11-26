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


class SearchResultItem(BaseModel):
    """Individual search result item."""

    content: str
    section_url: str
    source_url: str
    source_id: str
    name: str
    type: str
    category: str
    description: str
    content_source: str
    score: float = Field(..., description="Similarity score (0.0-1.0)")
    subcategory: Optional[str] = None


class SearchResponse(BaseModel):
    results: List[SearchResultItem]
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
    total_chunks: int = 0
    content_source: str = "external"


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


class SourceComparisonDetail(BaseModel):
    """Detail item for source comparison lists."""

    url: str
    name: Optional[str] = None


class KnowledgeBaseSourceStats(BaseModel):
    """Statistics for knowledge base sources."""

    total: int = Field(..., description="Total number of sources in knowledge base")
    internal: int = Field(..., description="Number of internal S3 sources")
    external: int = Field(..., description="Number of external crawled sources")
    total_chunks: int = Field(..., description="Total number of vector chunks")


class DatabaseSourceStats(BaseModel):
    """Statistics for database sources."""

    total: int = Field(..., description="Total number of sources in database")
    enabled: int = Field(..., description="Number of enabled sources")
    disabled: int = Field(..., description="Number of disabled sources")


class SourceComparisonMetrics(BaseModel):
    """Comparison metrics between knowledge base and database sources."""

    in_both: int = Field(..., description="Sources present in both KB and DB")
    only_in_kb: int = Field(..., description="Sources only in knowledge base")
    only_in_db: int = Field(..., description="Sources only in database")
    missing_from_kb_but_enabled: int = Field(
        ..., description="Enabled DB sources missing from knowledge base"
    )


class SourceComparisonDetails(BaseModel):
    """Detailed lists of sources in various comparison categories."""

    only_in_kb: List[SourceComparisonDetail] = Field(
        ..., description="Sources that exist only in knowledge base"
    )
    only_in_db: List[SourceComparisonDetail] = Field(
        ..., description="Sources that exist only in database"
    )
    missing_from_kb_but_enabled: List[SourceComparisonDetail] = Field(
        ..., description="Enabled database sources not found in knowledge base"
    )


class SourceComparisonResponse(BaseModel):
    """Complete response for source comparison endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "kb_sources": {
                    "total": 25,
                    "internal": 10,
                    "external": 15,
                    "total_chunks": 1250
                },
                "db_sources": {"total": 30, "enabled": 28, "disabled": 2},
                "comparison": {
                    "in_both": 20,
                    "only_in_kb": 5,
                    "only_in_db": 10,
                    "missing_from_kb_but_enabled": 8
                },
                "details": {
                    "only_in_kb": [
                        {"url": "https://example.com/doc1", "name": "Doc 1"}
                    ],
                    "only_in_db": [
                        {"url": "https://example.com/doc2", "name": "Doc 2"}
                    ],
                    "missing_from_kb_but_enabled": [
                        {"url": "https://example.com/doc3", "name": "Doc 3"}
                    ],
                },
            }
        }
    )

    kb_sources: KnowledgeBaseSourceStats
    db_sources: DatabaseSourceStats
    comparison: SourceComparisonMetrics
    details: SourceComparisonDetails



