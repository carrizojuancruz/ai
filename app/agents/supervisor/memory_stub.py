from __future__ import annotations

from typing import Any


class InMemoryStoreStub:
    def __init__(self) -> None:
        self._data: dict[tuple[str, ...], dict[str, Any]] = {}

    def put(self, namespace: tuple[str, ...], key: str, value: dict[str, Any]) -> None:
        if namespace not in self._data:
            self._data[namespace] = {}
        self._data[namespace][key] = value

    def get(self, namespace: tuple[str, ...], key: str) -> list[Any]:
        if namespace in self._data and key in self._data[namespace]:
            return [{"key": key, "value": self._data[namespace][key]}]
        return []

    def search(self, namespace: tuple[str, ...], query: str | None = None, limit: int = 5) -> list[Any]:
        items = list((self._data.get(namespace) or {}).items())[:limit]
        return [{"key": k, "value": v} for k, v in items]


