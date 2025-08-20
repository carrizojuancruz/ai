from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from knowledge.models import BulkSourceRequest, Source, SourceRequest
from knowledge.source_service import SourceService, get_source_service

router = APIRouter(prefix="/admin", tags=["Admin"])


class SourceResponse(BaseModel):
    source: Source
    documents_indexed: int
    success: bool
    message: str

@router.get("/sources")
async def get_sources(source_service: SourceService = Depends(get_source_service)) -> List[Source]:
    return await source_service.get_all_sources()


@router.get("/sources/{source_id}")
async def get_source(source_id: str, source_service: SourceService = Depends(get_source_service)) -> Source:
    source = await source_service.get_source_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.post("/sources")
async def create_source(request: SourceRequest, source_service: SourceService = Depends(get_source_service)) -> SourceResponse:
    result = await source_service.create_source(request)

    return SourceResponse(
        source=result["source"],
        documents_indexed=result["documents_indexed"],
        success=result["success"],
        message=result["message"]
    )


@router.post("/sources/bulk")
async def create_sources_bulk(request: BulkSourceRequest, source_service: SourceService = Depends(get_source_service)) -> dict:
    return await source_service.bulk_create_sources(request)


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str, source_service: SourceService = Depends(get_source_service)) -> dict:
    if not await source_service.delete_source(source_id):
        raise HTTPException(status_code=404, detail="Source not found")

    return {"message": "Source deleted successfully"}
