import logging
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, UploadFile

from app.core.config import config
from app.knowledge.constants import (
    VERA_GUIDANCE_CATEGORY,
    VERA_GUIDANCE_CONTENT_SOURCE,
    VERA_GUIDANCE_DESCRIPTION,
    VERA_GUIDANCE_NAME,
    VERA_GUIDANCE_TYPE,
)
from app.knowledge.models import Source
from app.knowledge.s3_sync_service import S3SyncService
from app.knowledge.service import KnowledgeService
from app.knowledge.unified_sync_service import UnifiedSyncService
from app.knowledge.utils import generate_source_id

from .schemas.knowledge import (
    DeleteAllVectorsResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SourceComparisonDetail,
    SourceComparisonResponse,
    SourceDetailsResponse,
    SourceResponse,
    SourcesResponse,
    SyncSourceRequest,
    SyncSourceResponse,
)

logger = logging.getLogger(__name__)

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
        result_items = [SearchResultItem(**r) for r in results]
        return SearchResponse(
            results=result_items,
            query=request.query,
            total_results=len(result_items)
        )
    except Exception as e:
        logger.error(f"Search failed for query '{request.query}': {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        ) from e


@router.get("/sources/comparison", response_model=SourceComparisonResponse)
async def get_sources_comparison() -> SourceComparisonResponse:
    """Compare knowledge base sources with external database sources."""
    try:
        from app.services.external_context.sources.repository import ExternalSourcesRepository

        knowledge_service = KnowledgeService()
        external_repo = ExternalSourcesRepository()

        # Get sources from vector store
        kb_sources = knowledge_service.get_sources()

        # Get sources from external database
        try:
            external_sources = await external_repo.get_all()
        except Exception as e:
            logger.error(f"Failed to fetch external sources: {str(e)}")
            external_sources = []

        # Build comparison metrics
        kb_urls = {s.url for s in kb_sources}
        external_urls = {s.url for s in external_sources}
        enabled_external_urls = {s.url for s in external_sources if s.enabled}

        in_both = kb_urls & external_urls
        only_in_kb = kb_urls - external_urls
        only_in_db = external_urls - kb_urls
        missing_from_kb = enabled_external_urls - kb_urls

        # Categorize sources
        kb_sources_categorized = {
            "internal": [s for s in kb_sources if s.content_source == "internal"],
            "external": [s for s in kb_sources if s.content_source == "external"]
        }

        external_sources_categorized = {
            "enabled": [s for s in external_sources if s.enabled],
            "disabled": [s for s in external_sources if not s.enabled]
        }

        return SourceComparisonResponse(
            kb_sources={
                "total": len(kb_sources),
                "internal": len(kb_sources_categorized["internal"]),
                "external": len(kb_sources_categorized["external"]),
                "total_chunks": sum(s.total_chunks for s in kb_sources)
            },
            db_sources={
                "total": len(external_sources),
                "enabled": len(external_sources_categorized["enabled"]),
                "disabled": len(external_sources_categorized["disabled"])
            },
            comparison={
                "in_both": len(in_both),
                "only_in_kb": len(only_in_kb),
                "only_in_db": len(only_in_db),
                "missing_from_kb_but_enabled": len(missing_from_kb)
            },
            details={
                "only_in_kb": [SourceComparisonDetail(url=url, name=next((s.name for s in kb_sources if s.url == url), None)) for url in sorted(only_in_kb)],
                "only_in_db": [SourceComparisonDetail(url=url, name=next((s.name for s in external_sources if s.url == url), None)) for url in sorted(only_in_db)],
                "missing_from_kb_but_enabled": [SourceComparisonDetail(url=url, name=next((s.name for s in external_sources if s.url == url), None)) for url in sorted(missing_from_kb)]
            }
        )
    except Exception as e:
        logger.error(f"Failed to compare sources: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to compare sources: {str(e)}"
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
                section_urls=source.section_urls or [],
                total_chunks=source.total_chunks,
                content_source=source.content_source
            )
            for source in sources
        ]

        return SourcesResponse(
            sources=source_responses,
            total_sources=len(source_responses)
        )
    except Exception as e:
        logger.error(f"Failed to retrieve sources: {str(e)}", exc_info=True)
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


@router.delete("/sources/{source_id}", response_model=DeleteAllVectorsResponse)
async def delete_source_vectors(source_id: str) -> DeleteAllVectorsResponse:
    """Delete all vectors for a specific source. This clears all chunks but does not delete the source metadata."""
    try:
        knowledge_service = KnowledgeService()
        result = knowledge_service.delete_source_vectors_by_id(source_id)

        return DeleteAllVectorsResponse(
            success=result["success"],
            vectors_deleted=result["vectors_deleted"],
            message=result.get("message", ""),
            vectors_failed=result.get("vectors_failed"),
            error=result.get("error")
        )
    except Exception as e:
        logger.error(f"Failed to delete vectors for source {source_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete vectors: {str(e)}"
        ) from e


@router.get("/vectors/count")
async def get_vectors_count():
    """Get the total count of vectors in S3."""
    try:
        knowledge_service = KnowledgeService()
        vector_keys = knowledge_service.vector_store_service._get_all_vector_keys()
        return {
            "total_vectors": len(vector_keys),
            "bucket": knowledge_service.vector_store_service.bucket_name,
            "index": knowledge_service.vector_store_service.index_name
        }
    except Exception as e:
        logger.error(f"Failed to count vectors: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to count vectors: {str(e)}"
        ) from e


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
        logger.error(f"Failed to delete all vectors: {str(e)}", exc_info=True)
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
        raise HTTPException(status_code=500, detail=result.get("error", "Upload failed"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload file to S3: {str(e)}", exc_info=True)
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
        logger.error(f"Failed to list S3 files with prefix '{prefix}': {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}") from e


@router.delete("/s3/files")
async def delete_all_s3_files():
    """Delete ALL files from S3 bucket and their vectors."""
    try:
        s3_sync_service = S3SyncService()
        result = s3_sync_service.delete_all_files()

        if result["success"]:
            return result
        raise HTTPException(status_code=500, detail=f"Bulk deletion failed: {result.get('error', 'Unknown error')}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk deletion of S3 files failed: {str(e)}", exc_info=True)
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
        raise HTTPException(status_code=500, detail=result.get("error", "Deletion failed"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete S3 file '{s3_key}': {str(e)}", exc_info=True)
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
        source_id = generate_source_id(url)

        source = Source(
            id=source_id,
            name=VERA_GUIDANCE_NAME,
            url=url,
            enabled=True,
            type=VERA_GUIDANCE_TYPE,
            category=VERA_GUIDANCE_CATEGORY,
            description=VERA_GUIDANCE_DESCRIPTION,
            recursion_depth=config.VERA_GUIDANCE_RECURSION_DEPTH
        )

        knowledge_service = KnowledgeService()
        result = await knowledge_service.upsert_source(
            source=source,
            content_source=VERA_GUIDANCE_CONTENT_SOURCE
        )

        if result["success"]:
            return {
                "success": True,
                "pages_crawled": result.get("documents_processed", 0),
                "chunks_created": result.get("documents_added", 0),
                "source_id": source.id
            }
        raise HTTPException(
            status_code=500,
            detail=result.get("message", "Sync failed")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Internal sync failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal sync failed: {str(e)}") from e


@router.post("/sync-source", response_model=SyncSourceResponse)
async def sync_single_source(request: SyncSourceRequest) -> SyncSourceResponse:
    """Synchronize a single knowledge base source by URL."""
    try:
        logger.info(f"Starting single-source sync for URL: {request.url}")

        knowledge_service = KnowledgeService()

        source_id = generate_source_id(request.url)
        logger.debug(f"Generated source_id: {source_id}")

        if not request.name:
            parsed = urlparse(request.url)
            request.name = f"Source from {parsed.netloc}"

        source = Source(
            id=source_id,
            name=request.name,
            url=request.url,
            enabled=True,
            type=request.type,
            category=request.category,
            description=request.description,
            include_path_patterns=request.include_path_patterns,
            exclude_path_patterns=request.exclude_path_patterns,
            total_max_pages=request.total_max_pages or 20,
            recursion_depth=request.recursion_depth or 2
        )

        logger.info(f"Attempting to sync source: {source.name} ({source.url})")

        result = await knowledge_service.upsert_source(
            source,
            content_source="external"
        )

        content_changed = result.get("documents_added", 0) > 0 or result.get("is_new_source", False)

        response = SyncSourceResponse(
            success=result["success"],
            source_url=source.url,
            source_id=source_id,
            is_new_source=result.get("is_new_source", False),
            documents_processed=result.get("documents_processed", 0),
            documents_added=result.get("documents_added", 0),
            processing_time_seconds=result.get("processing_time_seconds", 0.0),
            message=result.get("message", "Successfully synchronized source"),
            crawl_type=config.CRAWL_TYPE,
            content_changed=content_changed,
            error=result.get("error"),
            crawl_error=result.get("crawl_error")
        )

        if response.success:
            logger.info(
                f"Successfully synced {source.url}: "
                f"{response.documents_added} chunks added, "
                f"took {response.processing_time_seconds}s"
            )
        else:
            logger.error(f"Sync failed for {source.url}: {response.error}")

        return response

    except ValueError as e:
        logger.warning(f"Invalid request for sync: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid request: {str(e)}"
        ) from e

    except Exception as e:
        logger.error(f"Failed to sync source {request.url}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync source: {str(e)}"
        ) from e


@router.post("/sync-all")
async def sync_all_knowledge_sources():
    """Synchronize all knowledge base sources.

    Syncs: External sources (FOS API), S3 files, Vera guidance.
    Auto-uploads Profile.md if missing.
    """
    try:
        result = await UnifiedSyncService().sync_all_sources()
        return result
    except Exception as e:
        logger.error(f"Unified sync failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
