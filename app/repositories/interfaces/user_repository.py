from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.models.user import UserContext


class UserRepository(Protocol):
    async def get_by_id(self, user_id: UUID) -> UserContext | None:  # pragma: no cover - interface only
        ...

    async def upsert(self, user: UserContext) -> UserContext:  # pragma: no cover - interface only
        ...

    async def delete(self, user_id: UUID) -> None:  # pragma: no cover - interface only
        ...


