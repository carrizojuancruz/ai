from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4
from datetime import datetime, timezone

from langchain_core.runnables import RunnableConfig
from langgraph.config import get_store


def _utc_now_iso() -> str:
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


