from fastapi import APIRouter, HTTPException

from app.knowledge.service import KnowledgeService

from .schemas.knowledge import SearchRequest, SearchResponse, SourceResponse, SourcesResponse

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])

@router.post("/search", response_model=SearchResponse)
async def search_knowledge_base(request: SearchRequest) -> SearchResponse:
    """Search the knowledge base."""
    try:
        knowledge_service = KnowledgeService()
        results = await knowledge_service.search(request.query)
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
                name=source.name,
                url=source.url,
                type=source.type,
                category=source.category,
                description=source.description,
                include_path_patterns=source.include_path_patterns,
                exclude_path_patterns=source.exclude_path_patterns,
                total_max_pages=source.total_max_pages,
                recursion_depth=source.recursion_depth,
                last_sync=source.last_sync
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
