from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4
from datetime import datetime, timezone

from langchain_core.runnables import RunnableConfig
from langgraph.config import get_store


def _utc_now_iso() -> str:
    """
    Returns the current UTC time in ISO format.
    
    Returns:
        str: Current UTC time in ISO 8601 format.
    """
    return datetime.now(tz=timezone.utc).isoformat()


ALLOWED_CATEGORIES: set[str] = {
    "Finance",
    "Budget",
    "Goals",
    "Personal",
    "Education",
    "Conversation_Summary",
    "Other",
}


def _normalize_category(raw: Optional[str]) -> str:
    """
    Normalizes and validates a category string against allowed categories.
    
    Args:
        raw (Optional[str]): Raw category string to normalize.
        
    Returns:
        str: Normalized category string. If the raw string is empty/None or not in 
             allowed categories, returns "Other".
             
    Notes:
        - Converts underscores to spaces, applies title case, then back to underscores
        - Ensures the result matches one of the predefined ALLOWED_CATEGORIES
    """
    if not raw:
        return "Other"
    candidate = raw.replace("_", " ").strip().title().replace(" ", "_")
    return candidate if candidate in ALLOWED_CATEGORIES else "Other"


async def semantic_memory_search(
    topic: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 5,
    config: RunnableConfig = {},
) -> list[dict[str, Any]]:
    """
    Performs a semantic search in the user's memory using a vector store.
    
    Args:
        topic (Optional[str]): Optional category to filter the results (e.g., "python", "history").
        query (Optional[str]): Search query used to find semantically similar items.
        limit (int): Maximum number of results to return. Defaults to 5.
        config (RunnableConfig): Configuration dictionary, expected to include `user_id` inside `configurable`.
        
    Returns:
        list[dict[str, Any]]: A list of matched items, each represented as a dictionary.
        
    Notes:
        - The function searches within the namespace associated with the user (`user_id`) and the optional category.
        - If no items are found with the category filter, it retries the search without it.
    """
    store = get_store()
    user_id = config.get("configurable", {}).get("user_id")
    if not user_id:
        return []
    namespace = (user_id, "semantic")
    norm_topic = _normalize_category(topic) if isinstance(topic, str) else None
    user_filter = {"category": norm_topic} if norm_topic else None
    if not query:
        return []
    items = store.search(namespace, query=query, filter=user_filter, limit=limit)
    if not items and norm_topic:
        items = store.search(namespace, query=query, filter=None, limit=limit)
    return [i.value for i in items]


async def episodic_memory_fetch(
    topic: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 3,
    config: RunnableConfig = {},
) -> list[dict[str, Any]]:
    """
    Retrieves episodic memories from the user's memory store.
    
    Args:
        topic (Optional[str]): Optional category to filter the results (e.g., "conversation", "meeting").
        query (Optional[str]): Search query for finding relevant episodic memories.
        limit (int): Maximum number of results to return. Defaults to 3.
        config (RunnableConfig): Configuration dictionary, expected to include `user_id` inside `configurable`.
        
    Returns:
        list[dict[str, Any]]: A list of episodic memory items, each represented as a dictionary.
        
    Notes:
        - Searches within the episodic memory namespace for the specific user.
        - If no query is provided, defaults to "recent conversation" for general retrieval.
        - Falls back to unfiltered search if category-filtered search returns no results.
    """
    store = get_store()
    user_id = config.get("configurable", {}).get("user_id")
    if not user_id:
        return []
    namespace = (user_id, "episodic")
    norm_topic = _normalize_category(topic) if isinstance(topic, str) else None
    user_filter = {"category": norm_topic} if norm_topic else None
    eff_query = query or "recent conversation"
    items = store.search(namespace, query=eff_query, filter=user_filter, limit=limit)
    if not items and query:
        items = store.search(namespace, query=query, filter=None, limit=limit)
    return [i.value for i in items]


async def semantic_memory_put(
    summary: str,
    category: Optional[str] = None,
    key: Optional[str] = None,
    tags: Optional[list[str]] = None,
    source: Optional[str] = None,
    importance: Optional[int] = None,
    pinned: Optional[bool] = None,
    config: RunnableConfig = {},
) -> dict[str, Any]:
    """
    Stores a new semantic memory item in the user's memory store.
    
    Args:
        summary (str): The main content/summary of the memory item.
        category (Optional[str]): Category classification for the memory item.
        key (Optional[str]): Unique identifier for the memory item. If not provided, generates a UUID.
        tags (Optional[list[str]]): List of tags for categorizing and searching the memory.
        source (Optional[str]): Source of the memory (e.g., "chat", "email", "document"). Defaults to "chat".
        importance (Optional[int]): Importance level of the memory (1-10 scale). Defaults to 1.
        pinned (Optional[bool]): Whether the memory should be pinned for quick access. Defaults to False.
        config (RunnableConfig): Configuration dictionary, expected to include `user_id` inside `configurable`.
        
    Returns:
        dict[str, Any]: Response dictionary with operation status and created item details.
            - On success: {"ok": True, "key": str, "value": dict}
            - On failure: {"ok": False, "error": str}
            
    Notes:
        - Automatically normalizes the category using _normalize_category function.
        - Sets creation and last accessed timestamps to current UTC time.
        - Indexes the summary field for semantic search capabilities.
    """
    store = get_store()
    user_id = config.get("configurable", {}).get("user_id")
    if not user_id:
        return {"ok": False, "error": "missing_user_id"}
    namespace = (user_id, "semantic")
    eff_key = key or uuid4().hex
    now = _utc_now_iso()
    value: dict[str, Any] = {
        "id": eff_key,
        "user_id": user_id,
        "type": "semantic",
        "summary": summary,
        "category": _normalize_category(category),
        "tags": tags or [],
        "source": source or "chat",
        "importance": int(importance) if importance is not None else 1,
        "pinned": bool(pinned) if pinned is not None else False,
        "created_at": now,
        "last_accessed": now,
    }
    store.put(namespace, eff_key, value, index=["summary"])
    return {"ok": True, "key": eff_key, "value": value}


async def episodic_memory_put(
    summary: str,
    category: Optional[str] = None,
    key: Optional[str] = None,
    tags: Optional[list[str]] = None,
    source: Optional[str] = None,
    importance: Optional[int] = None,
    pinned: Optional[bool] = None,
    config: RunnableConfig = {},
) -> dict[str, Any]:
    """
    Stores a new episodic memory item in the user's memory store.
    
    Args:
        summary (str): The main content/summary of the episodic memory.
        category (Optional[str]): Category classification for the memory item.
        key (Optional[str]): Unique identifier for the memory item. If not provided, generates a UUID.
        tags (Optional[list[str]]): List of tags for categorizing and searching the memory.
        source (Optional[str]): Source of the memory (e.g., "chat", "meeting", "call"). Defaults to "chat".
        importance (Optional[int]): Importance level of the memory (1-10 scale). Defaults to 1.
        pinned (Optional[bool]): Whether the memory should be pinned for quick access. Defaults to False.
        config (RunnableConfig): Configuration dictionary, expected to include `user_id` inside `configurable`.
        
    Returns:
        dict[str, Any]: Response dictionary with operation status and created item details.
            - On success: {"ok": True, "key": str, "value": dict}
            - On failure: {"ok": False, "error": str}
            
    Notes:
        - Creates episodic memories which represent specific events or experiences.
        - Automatically normalizes the category using _normalize_category function.
        - Sets creation and last accessed timestamps to current UTC time.
        - Indexes the summary field for semantic search capabilities.
    """
    store = get_store()
    user_id = config.get("configurable", {}).get("user_id")
    if not user_id:
        return {"ok": False, "error": "missing_user_id"}
    namespace = (user_id, "episodic")
    eff_key = key or uuid4().hex
    now = _utc_now_iso()
    value: dict[str, Any] = {
        "id": eff_key,
        "user_id": user_id,
        "type": "episodic",
        "summary": summary,
        "category": _normalize_category(category),
        "tags": tags or [],
        "source": source or "chat",
        "importance": int(importance) if importance is not None else 1,
        "pinned": bool(pinned) if pinned is not None else False,
        "created_at": now,
        "last_accessed": now,
    }
    store.put(namespace, eff_key, value, index=["summary"])
    return {"ok": True, "key": eff_key, "value": value}


async def semantic_memory_update(
    key: str,
    summary: Optional[str] = None,
    category: Optional[str] = None,
    tags: Optional[list[str]] = None,
    importance: Optional[int] = None,
    pinned: Optional[bool] = None,
    config: RunnableConfig = {},
) -> dict[str, Any]:
    """
    Updates an existing semantic memory item in the user's memory store.
    
    Args:
        key (str): Unique identifier of the memory item to update.
        summary (Optional[str]): New summary content for the memory item.
        category (Optional[str]): New category classification for the memory item.
        tags (Optional[list[str]]): New list of tags for the memory item.
        importance (Optional[int]): New importance level for the memory item.
        pinned (Optional[bool]): New pinned status for the memory item.
        config (RunnableConfig): Configuration dictionary, expected to include `user_id` inside `configurable`.
        
    Returns:
        dict[str, Any]: Response dictionary with operation status and updated item details.
            - On success: {"ok": True, "key": str, "value": dict}
            - On failure: {"ok": False, "error": str}
            
    Notes:
        - Only updates the fields that are provided (None values are ignored).
        - Automatically normalizes the category if provided.
        - Updates the last_accessed timestamp to current UTC time.
        - Re-indexes the summary field if it was modified.
    """
    store = get_store()
    user_id = config.get("configurable", {}).get("user_id")
    if not user_id:
        return {"ok": False, "error": "missing_user_id"}
    namespace = (user_id, "semantic")
    existing = store.get(namespace, key)
    if not existing:
        return {"ok": False, "error": "not_found"}
    value = dict(existing.value)
    if summary is not None:
        value["summary"] = summary
    if category is not None:
        value["category"] = _normalize_category(category)
    if tags is not None:
        value["tags"] = list(tags)
    if importance is not None:
        value["importance"] = int(importance)
    if pinned is not None:
        value["pinned"] = bool(pinned)
    value["last_accessed"] = _utc_now_iso()
    store.put(namespace, key, value, index=["summary"])
    return {"ok": True, "key": key, "value": value}


async def episodic_memory_update(
    key: str,
    summary: Optional[str] = None,
    category: Optional[str] = None,
    tags: Optional[list[str]] = None,
    importance: Optional[int] = None,
    pinned: Optional[bool] = None,
    config: RunnableConfig = {},
) -> dict[str, Any]:
    """
    Updates an existing episodic memory item in the user's memory store.
    
    Args:
        key (str): Unique identifier of the episodic memory item to update.
        summary (Optional[str]): New summary content for the episodic memory.
        category (Optional[str]): New category classification for the episodic memory.
        tags (Optional[list[str]]): New list of tags for the episodic memory.
        importance (Optional[int]): New importance level for the episodic memory.
        pinned (Optional[bool]): New pinned status for the episodic memory.
        config (RunnableConfig): Configuration dictionary, expected to include `user_id` inside `configurable`.
        
    Returns:
        dict[str, Any]: Response dictionary with operation status and updated item details.
            - On success: {"ok": True, "key": str, "value": dict}
            - On failure: {"ok": False, "error": str}
            
    Notes:
        - Only updates the fields that are provided (None values are ignored).
        - Automatically normalizes the category if provided.
        - Updates the last_accessed timestamp to current UTC time.
        - Re-indexes the summary field if it was modified.
        - Episodic memories represent specific events or experiences that can be updated over time.
    """
    store = get_store()
    user_id = config.get("configurable", {}).get("user_id")
    if not user_id:
        return {"ok": False, "error": "missing_user_id"}
    namespace = (user_id, "episodic")
    existing = store.get(namespace, key)
    if not existing:
        return {"ok": False, "error": "not_found"}
    value = dict(existing.value)
    if summary is not None:
        value["summary"] = summary
    if category is not None:
        value["category"] = _normalize_category(category)
    if tags is not None:
        value["tags"] = list(tags)
    if importance is not None:
        value["importance"] = int(importance)
    if pinned is not None:
        value["pinned"] = bool(pinned)
    value["last_accessed"] = _utc_now_iso()
    store.put(namespace, key, value, index=["summary"])
    return {"ok": True, "key": key, "value": value}


