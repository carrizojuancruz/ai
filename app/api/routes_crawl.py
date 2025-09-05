import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.knowledge.crawler.service import CrawlerService
from app.knowledge.document_service import DocumentService
from app.knowledge.models import Source

router = APIRouter(prefix="/crawl", tags=["Crawling"])


class CrawlRequest(BaseModel):
    """Request model for crawling a URL."""

    url: str


class ChunkResponse(BaseModel):
    """Response model for a single chunk."""

    content: str
    section_url: str
    source_url: str
    name: str
    type: str
    category: str
    description: str
    content_hash: str


class CrawlResponse(BaseModel):
    """Response model for crawl results."""

    url: str
    total_documents: int
    total_chunks: int
    chunks: List[ChunkResponse]
    message: str


@router.post("/crawl", response_model=CrawlResponse)
async def crawl_url(request: CrawlRequest) -> CrawlResponse:
    """Crawl a URL and return chunked content without embedding."""
    try:
        # Create a temporary source object for crawling
        temp_source = Source(
            id=str(uuid.uuid4()),
            name=f"Temporary crawl of {request.url}",
            url=request.url,
            enabled=True,
            type="Temporary",
            category="Crawl Test",
            description=f"Temporary crawl for {request.url}",
            total_max_pages=20,  # Default limit
            recursion_depth=2,   # Default depth
            last_sync=datetime.now()
        )

        # Initialize services
        crawler_service = CrawlerService()
        document_service = DocumentService()

        # Crawl the source
        crawl_result = await crawler_service.crawl_source(temp_source)
        
        if "error" in crawl_result:
            raise HTTPException(
                status_code=400,
                detail=f"Crawling failed: {crawl_result['message']}"
            )

        documents = crawl_result.get("documents", [])
        
        if not documents:
            return CrawlResponse(
                url=request.url,
                total_documents=0,
                total_chunks=0,
                chunks=[],
                message="No content found at the provided URL"
            )

        chunks = document_service.split_documents(documents, temp_source)

        chunk_responses = []
        for chunk in chunks:
            chunk_responses.append(ChunkResponse(
                content=chunk.page_content,
                section_url=chunk.metadata.get("section_url", ""),
                source_url=chunk.metadata.get("source_url", ""),
                name=chunk.metadata.get("name", ""),
                type=chunk.metadata.get("type", ""),
                category=chunk.metadata.get("category", ""),
                description=chunk.metadata.get("description", ""),
                content_hash=chunk.metadata.get("content_hash", "")
            ))

        return CrawlResponse(
            url=request.url,
            total_documents=len(documents),
            total_chunks=len(chunks),
            chunks=chunk_responses,
            message=f"Successfully crawled and chunked content from {request.url}"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Crawl failed: {str(e)}"
        ) from e
