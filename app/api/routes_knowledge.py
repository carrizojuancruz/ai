from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.knowledge.service import KnowledgeService

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])


class SearchRequest(BaseModel):
    query: str
    limit: int = 5


class SearchResponse(BaseModel):
    results: list
    query: str
    total_results: int


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
