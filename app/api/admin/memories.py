from __future__ import annotations

import logging
from typing import Annotated, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.app_state import get_fos_nudge_manager
from app.services.memory_service import memory_service
from app.services.nudges.fos_manager import FOSNudgeManager

router = APIRouter(prefix="/admin/memories", tags=["Admin Memories"])
logger = logging.getLogger(__name__)


class MemoryItem(BaseModel):
    key: str
    namespace: List[str]
    score: Optional[float] = None
    value: dict[str, Any]


class MemorySearchResponse(BaseModel):
    ok: bool
    count: int
    total: int
    items: List[MemoryItem]


class MemoryGetResponse(BaseModel):
    key: str
    namespace: List[str]
    value: dict[str, Any]


class MemoryDeleteResponse(BaseModel):
    ok: bool
    message: str
    key: Optional[str] = None
    deleted_count: Optional[int] = None
    failed_count: Optional[int] = None
    total_found: Optional[int] = None


@router.get("/")
async def get_all_memories(
    memory_type: Optional[str] = Query(None, description="Memory type: semantic, episodic, or None for all types"),
    category: Optional[str] = Query(None, description="Optional category filter"),
    limit: int = Query(1000, description="Max memories to return", ge=1, le=10000),
) -> MemorySearchResponse:
    """Get all memories across all users."""
    try:
        all_memories = memory_service.get_all_memories(
            memory_type=memory_type,
            category=category,
            limit=limit,
        )

        items = [MemoryItem(**item) for item in all_memories]
        return MemorySearchResponse(
            ok=True,
            count=len(items),
            total=len(items),
            items=items,
        )

    except Exception as e:
        logger.error(f"Failed to retrieve all memories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve all memories: {str(e)}") from e


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
    - **user_id**: User ID to retrieve memories for
    - **memory_type**: Type of memories (semantic or episodic)
    - **category**: Optional category filter
    - **search**: Optional text search within memory summaries
    - **limit**: Maximum number of items to return (1-500, default 50)
    - **offset**: Offset for pagination
    """
    try:
        all_memories = memory_service.get_memories(
            user_id=user_id,
            memory_type=memory_type,
            search=search,
            category=category,
        )

        total_count = len(all_memories)
        paginated_memories = all_memories[offset : offset + limit]

        items = [MemoryItem(**item) for item in paginated_memories]
        return MemorySearchResponse(
            ok=True,
            count=len(items),
            total=total_count,
            items=items,
        )

    except ValueError as e:
        logger.warning(f"Invalid request: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to retrieve memories: {e}", exc_info=True)
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
    memory_type: str = Query("semantic", description="Memory type: semantic or episodic"),
    fos_manager: Annotated[Optional[FOSNudgeManager], Depends(get_fos_nudge_manager)] = None
) -> MemoryDeleteResponse:
    """Delete a single memory by key and its associated nudges.

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

        if result["ok"] and fos_manager:
            try:
                await fos_manager.delete_nudges_by_memory_id(memory_key)
                logger.info(f"Deleted nudges for memory {memory_key}")
            except Exception as e:
                logger.error(f"Failed to delete nudges for memory {memory_key}: {e}")

        return MemoryDeleteResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{user_id}")
async def delete_all_memories(
    user_id: str,
    memory_type: str = Query("semantic", description="Memory type: semantic or episodic"),
    confirm: bool = Query(False, description="Must be true to confirm deletion"),
    fos_manager: Annotated[Optional[FOSNudgeManager], Depends(get_fos_nudge_manager)] = None
) -> MemoryDeleteResponse:
    """Delete all memories for a user and type, and their associated nudges.

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
            memory_type=memory_type,
        )

        if result["deleted_count"] > 0 and fos_manager:
            try:
                await fos_manager.delete_nudges_by_user_id(user_id)
                logger.info(f"Successfully deleted nudges for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to delete nudges for user {user_id}: {e}", exc_info=True)

        return MemoryDeleteResponse(
            ok=result["ok"],
            message=result["message"],
            deleted_count=result["deleted_count"],
            failed_count=result["failed_count"],
            total_found=result["total_found"],
        )

    except ValueError as e:
        logger.warning(f"Invalid request: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to delete memories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete memories: {str(e)}") from e


@router.get("/supervisor/routing/procedural")
async def list_supervisor_routing_procedural():
    """List all supervisor procedural routing memories.

    Returns:
        {
            "ok": true,
            "count": 7,
            "items": [{"key": "...", "summary": "...", "category": "Routing"}]
        }

    """
    try:
        items = memory_service.list_supervisor_routing_memories()

        return {
            "ok": True,
            "count": len(items),
            "items": items
        }

    except Exception as e:
        logger.error(f"Endpoint error listing supervisor routing memories: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"ok": False, "error": "search_failed"}
        ) from e


