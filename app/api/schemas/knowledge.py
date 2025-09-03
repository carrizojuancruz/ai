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
    total_max_pages: Optional[int] = None
    recursion_depth: Optional[int] = None
    last_sync: Optional[datetime] = None


class SourcesResponse(BaseModel):
    """Response model for sources list."""

    sources: list[SourceResponse]
    total_sources: int


class ChunkMetadata(BaseModel):
    """Metadata for a single chunk."""

    content_preview: str
    content_length: Optional[int] = None
    estimated_tokens: Optional[int] = None
    section_url: str
    chunk_index: int
    content_hash: str
    vector_key: str
    content: Optional[str] = None  # Full content when available


class ChunkInfo(BaseModel):
    """Information about chunks for a source."""

    total_chunks: int
    unique_content_hashes: int
    total_characters: Optional[int] = None
    total_estimated_tokens: Optional[int] = None
    estimated_embedding_cost: Optional[float] = None
    sample_chunks: list[ChunkMetadata]
    all_chunks: Optional[list[ChunkMetadata]] = None


class SourceDetailsResponse(BaseModel):
    """Detailed response model for a single source with chunk information."""

    source: SourceResponse
    chunks: ChunkInfo
