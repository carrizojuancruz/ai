from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from unittest.mock import patch

import pytest

from app.agents.supervisor.memory.hotpath import _utc_now_iso, _write_semantic_memory


@dataclass
class FakeItem:
    key: str
    value: dict[str, Any]
    created_at: str
    updated_at: str
    score: Optional[float] = None
    namespace: tuple[str, ...] = ()


class FakeStore:
    def __init__(self, items: dict[str, dict[str, Any]]) -> None:
        self._items: dict[str, dict[str, Any]] = dict(items)
        self._created: dict[str, str] = {k: v.get("created_at") or _utc_now_iso() for k, v in items.items()}
        self._updated: dict[str, str] = {k: v.get("updated_at") or _utc_now_iso() for k, v in items.items()}
        self._last_search: list[FakeItem] = []
        self._last_put_key: Optional[str] = None

    def search(self, namespace: tuple[str, ...], *, query: str, filter: dict[str, Any], limit: int) -> list[FakeItem]:
        out = []
        for key, value in self._items.items():
            if filter and "category" in filter and value.get("category") != filter["category"]:
                continue
            out.append(
                FakeItem(
                    key=key,
                    value=dict(value),
                    created_at=self._created.get(key) or _utc_now_iso(),
                    updated_at=self._updated.get(key) or _utc_now_iso(),
                    score=value.get("_score", 0.0),
                    namespace=namespace,
                )
            )
        self._last_search = out[:limit]
        return out[:limit]

    def get(self, namespace: tuple[str, ...], key: str) -> Optional[FakeItem]:
        if key not in self._items:
            return None
        value = self._items[key]
        return FakeItem(
            key=key,
            value=dict(value),
            created_at=self._created.get(key) or _utc_now_iso(),
            updated_at=self._updated.get(key) or _utc_now_iso(),
            score=None,
            namespace=namespace,
        )

    def put(self, namespace: tuple[str, ...], key: str, value: dict[str, Any], index: list[str] | None = None) -> None:
        now = _utc_now_iso()
        if key not in self._items:
            self._created[key] = now
        prev_score = None
        if key in self._items:
            prev_score = self._items[key].get("_score")
        self._items[key] = dict(value)
        if prev_score is not None:
            self._items[key]["_score"] = prev_score
        self._updated[key] = now
        self._last_put_key = key

    def delete(self, namespace: tuple[str, ...], key: str) -> None:
        self._items.pop(key, None)
        self._created.pop(key, None)
        self._updated.pop(key, None)


@pytest.mark.asyncio
async def test_display_summary_updates_on_fallback_merge(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Fallback merge should update display_summary using candidate_value.
      - Neighbor exists with score [FALLBACK_LOW, CHECK_LOW)
      - Same-fact classifier returns True
      - After update, display_summary matches candidate_value
    """
    user_id = "u123"
    thread_id = None
    category = "Personal"
    existing_key = "mem_dog"
    existing_summary = "the user has a dog"
    existing_display = "you have a dog"

    store = FakeStore(
        {
            existing_key: {
                "id": existing_key,
                "user_id": user_id,
                "type": "semantic",
                "summary": existing_summary,
                "display_summary": existing_display,
                "category": category,
                "importance": 2,
                "created_at": _utc_now_iso(),
                "last_accessed": None,
                "_score": 0.5,
            }
        }
    )

    with (
        patch("app.agents.supervisor.memory.hotpath.get_store", return_value=store),
        patch("app.agents.supervisor.memory.hotpath.memory_service.create_memory", return_value=None),
        patch("app.agents.supervisor.memory.hotpath._has_min_token_overlap", return_value=True),
        patch("app.agents.supervisor.memory.hotpath._same_fact_classify", return_value=True),
        patch("app.agents.supervisor.memory.hotpath.AUTO_UPDATE", 0.95),
        patch("app.agents.supervisor.memory.hotpath.CHECK_LOW", 0.8),
        patch("app.agents.supervisor.memory.hotpath.FALLBACK_ENABLED", True),
        patch("app.agents.supervisor.memory.hotpath.FALLBACK_LOW", 0.4),
        patch("app.agents.supervisor.memory.hotpath.FALLBACK_TOPK", 3),
        patch("app.agents.supervisor.memory.hotpath.FALLBACK_RECENCY_DAYS", 365),
        patch("app.agents.supervisor.memory.hotpath.FALLBACK_CATEGORIES", None),
    ):
        candidate_summary = "the user has a dog and two cats"
        candidate_display = "you have a dog and two cats"
        candidate_value = {
            "id": "new_id",
            "user_id": user_id,
            "type": "semantic",
            "summary": candidate_summary,
            "display_summary": candidate_display,
            "category": category,
            "source": "chat",
            "importance": 3,
            "created_at": _utc_now_iso(),
            "last_accessed": None,
            "last_used_at": None,
        }

        await _write_semantic_memory(
            user_id=user_id,
            thread_id=thread_id,
            category=category,
            summary=candidate_summary,
            candidate_value=candidate_value,
            mem_type="semantic",
            candidate_id="candidate123",
        )

    updated = store.get((user_id, "semantic"), existing_key)
    assert updated is not None
    assert updated.value.get("display_summary") == candidate_display


@pytest.mark.asyncio
async def test_display_summary_updates_on_recreate_merge() -> None:
    """
    Recreate merge should compose display_summary and prefer the more informative candidate.
    """
    user_id = "u999"
    thread_id = None
    category = "Personal"
    existing_key = "mem_pet"
    existing_display = "you have a dog"

    store = FakeStore(
        {
            existing_key: {
                "id": existing_key,
                "user_id": user_id,
                "type": "semantic",
                "summary": "the user has a dog",
                "display_summary": existing_display,
                "category": category,
                "importance": 2,
                "created_at": _utc_now_iso(),
                "last_accessed": None,
                "_score": 0.99,
            }
        }
    )

    candidate_summary = "the user has a dog and two cats"
    candidate_display = "you have a dog and two cats"
    candidate_value = {
        "id": "new_id",
        "user_id": user_id,
        "type": "semantic",
        "summary": candidate_summary,
        "display_summary": candidate_display,
        "category": category,
        "source": "chat",
        "importance": 3,
        "created_at": _utc_now_iso(),
        "last_accessed": None,
        "last_used_at": None,
    }

    with (
        patch("app.agents.supervisor.memory.hotpath.get_store", return_value=store),
        patch("app.agents.supervisor.memory.hotpath.MERGE_MODE", "recreate"),
        patch("app.agents.supervisor.memory.hotpath.AUTO_UPDATE", 0.5),
    ):
        await _write_semantic_memory(
            user_id=user_id,
            thread_id=thread_id,
            category=category,
            summary=candidate_summary,
            candidate_value=candidate_value,
            mem_type="semantic",
            candidate_id="cand-xyz",
        )

    keys = list(store._items.keys())
    assert len(keys) == 1
    new_key = keys[0]
    assert new_key != existing_key

    updated = store.get((user_id, "semantic"), new_key)
    assert updated is not None
    assert updated.value.get("display_summary") == candidate_display
