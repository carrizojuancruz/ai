import hashlib

from fastapi import APIRouter, HTTPException, UploadFile

from app.core.config import config
from app.knowledge.models import Source
from app.knowledge.s3_sync_service import S3SyncService
from app.knowledge.service import KnowledgeService

from .schemas.knowledge import (
    DeleteAllVectorsResponse,
    SearchRequest,
    SearchResponse,
    SourceDetailsResponse,
    SourceResponse,
    SourcesResponse,
)

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])

@router.post("/search", response_model=SearchResponse)
async def search_knowledge_base(request: SearchRequest) -> SearchResponse:
    """Search the knowledge base with optional metadata filtering.

    The filter parameter allows you to narrow search results by metadata fields:
    - content_source: "internal" (S3 files) or "external" (crawled content)
    - file_type: "markdown", "text", "json", "html", "csv"
    - Other metadata fields as needed

    Examples:
        # Search all content
        POST /knowledge/search
        {"query": "How do I connect my bank?"}

        # Search only internal S3 files
        POST /knowledge/search
        {"query": "How do I connect my bank?", "filter": {"content_source": "internal"}}

        # Search only external crawled content
        POST /knowledge/search
        {"query": "Investment strategies", "filter": {"content_source": "external"}}

        # Search markdown files only
        POST /knowledge/search
        {"query": "API documentation", "filter": {"file_type": "markdown"}}

    """
    try:
        knowledge_service = KnowledgeService()
        results = await knowledge_service.search(request.query, filter=request.filter)
        return SearchResponse(
            results=results,
            query=request.query,
            total_results=len(results)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        ) from e


@router.get("/sources", response_model=SourcesResponse)
async def get_sources() -> SourcesResponse:
    """Get all knowledge base sources."""
    try:
        knowledge_service = KnowledgeService()
        sources = knowledge_service.get_sources()

        source_responses = [
            SourceResponse(
                id=source.id,
                name=source.name,
                url=source.url,
                type=source.type,
                category=source.category,
                description=source.description,
                include_path_patterns=source.include_path_patterns,
                exclude_path_patterns=source.exclude_path_patterns,
                total_max_pages=source.total_max_pages,
                recursion_depth=source.recursion_depth,
                last_sync=source.last_sync,
                section_urls=source.section_urls or []
            )
            for source in sources
        ]

        return SourcesResponse(
            sources=source_responses,
            total_sources=len(source_responses)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve sources: {str(e)}"
        ) from e


@router.get("/sources/{source_id}", response_model=SourceDetailsResponse)
async def get_source_details(source_id: str) -> SourceDetailsResponse:
    """Get basic details about a source and its chunks."""
    try:
        knowledge_service = KnowledgeService()
        details = knowledge_service.get_source_details(source_id)

        if "error" in details:
            raise HTTPException(status_code=404, detail=details["error"])

        return SourceDetailsResponse(
            source=details["source"],
            total_chunks=details["total_chunks"],
            chunks=details["chunks"]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get details: {str(e)}") from e


@router.delete("/vectors", response_model=DeleteAllVectorsResponse)
async def delete_all_vectors() -> DeleteAllVectorsResponse:
    """Delete ALL vectors from the knowledge base index. WARNING: This operation cannot be undone."""
    try:
        knowledge_service = KnowledgeService()
        result = knowledge_service.delete_all_vectors()

        return DeleteAllVectorsResponse(
            success=result["success"],
            vectors_deleted=result["vectors_deleted"],
            message=result["message"],
            vectors_failed=result.get("vectors_failed"),
            error=result.get("error")
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete all vectors: {str(e)}"
        ) from e



@router.post("/s3/upload")
async def upload_file_to_s3(file: UploadFile, s3_key: str | None = None):
    """Upload a file to S3 bucket.

    Args:
        file: File to upload
        s3_key: Optional S3 key (defaults to filename)

    Returns:
        Upload result with s3_key, s3_uri, bucket

    Example:
        curl -X POST "/knowledge/s3/upload" -F "file=@guide.md"

    """
    import tempfile
    from pathlib import Path

    try:
        s3_sync_service = S3SyncService()

        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        result = s3_sync_service.upload_file(temp_path, s3_key or file.filename)

        Path(temp_path).unlink(missing_ok=True)

        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Upload failed"))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}") from e


@router.get("/s3/files")
async def list_s3_files(prefix: str = ""):
    """List all files in S3 bucket with optional prefix filter.

    Args:
        prefix: Optional prefix to filter files

    Returns:
        List of files with metadata

    Examples:
        GET /knowledge/s3/files
        GET /knowledge/s3/files?prefix=guides/

    """
    try:
        s3_sync_service = S3SyncService()
        files = s3_sync_service.list_files(prefix)

        return {
            "bucket": s3_sync_service.bucket_name,
            "prefix": prefix,
            "count": len(files),
            "files": files
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}") from e


@router.delete("/s3/files")
async def delete_all_s3_files():
    """Delete ALL files from S3 bucket and their vectors."""
    try:
        s3_sync_service = S3SyncService()
        result = s3_sync_service.delete_all_files()

        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Bulk deletion failed"))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk deletion failed: {str(e)}") from e


@router.delete("/s3/{s3_key:path}")
async def delete_s3_file(s3_key: str, delete_vectors: bool = True):
    """Delete a file from S3 and optionally its vectors.

    Args:
        s3_key: S3 key of file to delete
        delete_vectors: Whether to also delete vectors (default: true)

    Returns:
        Deletion result with status and vector count

    Examples:
        DELETE /knowledge/s3/guide.md
        DELETE /knowledge/s3/guide.md?delete_vectors=false

    """
    try:
        s3_sync_service = S3SyncService()
        result = s3_sync_service.delete_file(s3_key, delete_vectors)

        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Deletion failed"))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}") from e


@router.post("/s3/sync")
async def sync_s3_to_vectors(s3_key: str | None = None, sync_all: bool = False, prefix: str = ""):
    """Sync S3 files to vector store.

    Args:
        s3_key: Specific file to sync (mutually exclusive with sync_all)
        sync_all: Sync all files in bucket (mutually exclusive with s3_key)
        prefix: Optional prefix for bulk sync (used with sync_all)

    Returns:
        Sync results with success/failure counts

    Examples:
        # Sync single file
        POST /knowledge/s3/sync?s3_key=guide.md

        # Sync all files
        POST /knowledge/s3/sync?sync_all=true

        # Sync files with prefix
        POST /knowledge/s3/sync?sync_all=true&prefix=guides/

    """
    try:
        if not s3_key and not sync_all:
            raise HTTPException(
                status_code=400,
                detail="Must provide either s3_key or sync_all=true"
            )

        if s3_key and sync_all:
            raise HTTPException(
                status_code=400,
                detail="Cannot specify both s3_key and sync_all"
            )

        s3_sync_service = S3SyncService()

        if s3_key:
            result = await s3_sync_service.sync_file(s3_key)
            if not result["success"]:
                raise HTTPException(status_code=500, detail=result.get("error", "Sync failed"))
            return result

        if sync_all:
            result = await s3_sync_service.sync_all(prefix)
            return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}") from e


@router.post("/sync/internal")
async def sync_internal_guidance():
    """Sync internal guidance web pages to knowledge base."""
    try:
        if not config.VERA_GUIDANCE_URL:
            raise HTTPException(status_code=400, detail="VERA_GUIDANCE_URL not configured")

        url = config.VERA_GUIDANCE_URL
        source_id = hashlib.sha256(url.encode()).hexdigest()[:16]

        source = Source(
            id=source_id,
            name="Vera In-App Guidance",
            url=url,
            enabled=True,
            type="Internal Documentation",
            category="In-App Guidance",
            description="Vera help center documentation",
            recursion_depth=config.VERA_GUIDANCE_RECURSION_DEPTH
        )

        knowledge_service = KnowledgeService()
        result = await knowledge_service.upsert_source(
            source=source,
            content_source="internal"
        )

        if result["success"]:
            return {
                "success": True,
                "pages_crawled": result.get("documents_processed", 0),
                "chunks_created": result.get("documents_added", 0),
                "source_id": source.id
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "Sync failed")
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal sync failed: {str(e)}") from e
