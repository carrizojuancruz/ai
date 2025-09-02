from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional, Union

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator

from app.services.memory_service import memory_service

router = APIRouter(prefix="/admin/memories", tags=["Admin Memories"])


class MemoryItem(BaseModel):
    key: str
    namespace: List[str]
    created_at: Optional[Union[str, datetime]] = None
    updated_at: Optional[Union[str, datetime]] = None
    score: Optional[float] = None
    value: dict[str, Any]

    @field_validator('created_at', 'updated_at', mode='before')
    @classmethod
    def convert_datetime_to_string(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v


class MemorySearchResponse(BaseModel):
    ok: bool
    count: int
    items: List[MemoryItem]


class MemoryGetResponse(BaseModel):
    key: str
    namespace: List[str]
    created_at: Optional[Union[str, datetime]] = None
    updated_at: Optional[Union[str, datetime]] = None
    value: dict[str, Any]

    @field_validator('created_at', 'updated_at', mode='before')
    @classmethod
    def convert_datetime_to_string(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v


class MemoryDeleteResponse(BaseModel):
    ok: bool
    message: str
    key: Optional[str] = None
    deleted_count: Optional[int] = None
    failed_count: Optional[int] = None
    total_found: Optional[int] = None

@router.get("/{user_id}")
async def get_memories(
    user_id: str,
    memory_type: str = Query("semantic", description="Memory type: semantic or episodic"),
    category: Optional[str] = Query(None, description="Optional category filter"),
    search: Optional[str] = Query(None, description="Optional text search within memory summaries"),
    limit: int = Query(50, description="Max items to return", ge=1, le=500),
    offset: int = Query(0, description="Offset for paging", ge=0),
) -> MemorySearchResponse:
    """Get all memories for a user with optional filtering.

    This endpoint retrieves ALL memories for display in settings/profile views.
    Use filters to narrow down results as needed.

    - **user_id**: User ID to retrieve memories for
    - **memory_type**: Type of memories (semantic or episodic)
    - **category**: Optional category filter
    - **search**: Optional text search within memory summaries
    - **limit**: Maximum number of items to return (1-500, default 50)
    - **offset**: Offset for pagination
    """
    try:
        result = memory_service.get_memories(
            user_id=user_id,
            memory_type=memory_type,
            category=category,
            search=search,
            limit=limit,
            offset=offset
        )

        items = [MemoryItem(**item) for item in result["items"]]
        return MemorySearchResponse(ok=result["ok"], count=result["count"], items=items)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve memories: {str(e)}") from e


@router.get("/{user_id}/{memory_key}")
async def get_memory_by_key(
    user_id: str,
    memory_key: str,
    memory_type: str = Query("semantic", description="Memory type: semantic or episodic")
) -> MemoryGetResponse:
    """Get a single memory by key.

    - **user_id**: User ID
    - **memory_key**: Memory key to retrieve
    - **memory_type**: Type of memory (semantic or episodic)
    """
    try:
        result = memory_service.get_memory_by_key(
            user_id=user_id,
            memory_key=memory_key,
            memory_type=memory_type
        )

        return MemoryGetResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve memory: {str(e)}") from e


@router.delete("/{user_id}/{memory_key}")
async def delete_memory_by_key(
    user_id: str,
    memory_key: str,
    memory_type: str = Query("semantic", description="Memory type: semantic or episodic")
) -> MemoryDeleteResponse:
    """Delete a single memory by key.

    - **user_id**: User ID
    - **memory_key**: Memory key to delete
    - **memory_type**: Type of memory (semantic or episodic)
    """
    try:
        result = memory_service.delete_memory_by_key(
            user_id=user_id,
            memory_key=memory_key,
            memory_type=memory_type
        )

        return MemoryDeleteResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{user_id}")
async def delete_all_memories(
    user_id: str,
    memory_type: str = Query("semantic", description="Memory type: semantic or episodic"),
    confirm: bool = Query(False, description="Must be true to confirm deletion")
) -> MemoryDeleteResponse:
    """Delete all memories for a user and type.

    **WARNING**: This will delete ALL memories for the specified user and type.
    Set confirm=true to proceed.

    - **user_id**: User ID
    - **memory_type**: Type of memories to delete (semantic or episodic)
    - **confirm**: Must be true to confirm deletion
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Deletion not confirmed. Set confirm=true to proceed with deleting all memories."
        )

    try:
        result = memory_service.delete_all_memories(
            user_id=user_id,
            memory_type=memory_type
        )

        return MemoryDeleteResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete memories: {str(e)}") from e
