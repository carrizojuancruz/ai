from fastapi import APIRouter, HTTPException

from app.knowledge.service import KnowledgeService

from .schemas.knowledge import SearchRequest, SearchResponse

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
