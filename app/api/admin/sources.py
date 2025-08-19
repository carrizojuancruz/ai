from typing import List
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from knowledge.service import get_knowledge_service
from knowledge.repository import SourceRepository
from knowledge.crawler.service import CrawlerService
from knowledge.models import SourceRequest, BulkSourceRequest, Source

router = APIRouter(prefix="/admin", tags=["Admin"])


class SourceResponse(BaseModel):
    source: Source
    documents_indexed: int
    success: bool
    message: str


source_repo = SourceRepository()
crawler_service = CrawlerService(source_repo)

@router.get("/sources")
async def get_sources() -> List[Source]:
    return source_repo.load_all()


@router.get("/sources/{source_id}")
async def get_source(source_id: str) -> Source:
    source = source_repo.find_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.post("/sources")
async def create_source(request: SourceRequest) -> SourceResponse:
    source = Source(
        id=str(uuid4()),
        name=request.name,
        url=request.url
    )
    
    source_repo.add(source)
    
    try:
        crawl_result = await crawler_service.crawl_source(source.id)
        documents = crawl_result.get("documents", [])
        
        if documents:
            kb_service = get_knowledge_service()
            index_result = kb_service.update_documents_for_source(documents, source.id)
            
            return SourceResponse(
                source=source,
                documents_indexed=index_result.get("documents_added", 0),
                success=True,
                message=f"Source created and {len(documents)} documents indexed"
            )
        else:
            return SourceResponse(
                source=source,
                documents_indexed=0,
                success=True,
                message="Source created but no documents found"
            )
    
    except Exception as e:
        return SourceResponse(
            source=source,
            documents_indexed=0,
            success=False,
            message=f"Source created but crawl failed: {str(e)}"
        )


@router.post("/sources/bulk")
async def create_sources_bulk(request: BulkSourceRequest) -> dict:
    results = []
    
    for source_request in request.sources:
        source = Source(
            id=str(uuid4()),
            name=source_request.name,
            url=source_request.url
        )
        
        source_repo.add(source)
        
        try:
            crawl_result = await crawler_service.crawl_source(source.id)
            documents = crawl_result.get("documents", [])
            
            if documents:
                kb_service = get_knowledge_service()
                index_result = kb_service.update_documents_for_source(documents, source.id)
                
                results.append(SourceResponse(
                    source=source,
                    documents_indexed=index_result.get("documents_added", 0),
                    success=True,
                    message=f"{len(documents)} documents indexed"
                ))
            else:
                results.append(SourceResponse(
                    source=source,
                    documents_indexed=0,
                    success=True,
                    message="No documents found"
                ))
        
        except Exception as e:
            results.append(SourceResponse(
                source=source,
                documents_indexed=0,
                success=False,
                message=f"Crawl failed: {str(e)}"
            ))
    
    total_sources = len(results)
    successful_crawls = sum(1 for r in results if r.success)
    total_documents = sum(r.documents_indexed for r in results)
    
    return {
        "sources_created": total_sources,
        "successful_crawls": successful_crawls,
        "total_documents_indexed": total_documents,
        "results": results
    }


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str) -> dict:
    if not source_repo.delete_by_id(source_id):
        raise HTTPException(status_code=404, detail="Source not found")
    
    try:
        kb_service = get_knowledge_service()
        kb_service.vector_store.delete_documents(source_id)
    except Exception:
        pass
    
    return {"message": "Source deleted successfully"}
