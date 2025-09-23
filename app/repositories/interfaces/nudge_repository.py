from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.models.nudge import NudgeRecord


class NudgeRepository(Protocol):
    async def create_nudge(self, nudge: NudgeRecord) -> NudgeRecord:  # pragma: no cover - interface only
        ...

    async def get_user_nudges(self, user_id: UUID, status: str | None = None, limit: int = 100) -> list[NudgeRecord]:  # pragma: no cover - interface only
        ...

    async def mark_processing(self, nudge_ids: list[UUID]) -> list[NudgeRecord]:  # pragma: no cover - interface only
        ...

    async def update_status(self, nudge_id: UUID, status: str, processed_at: bool = False) -> NudgeRecord | None:  # pragma: no cover - interface only
        ...

    async def delete_by_ids(self, nudge_ids: list[UUID]) -> int:  # pragma: no cover - interface only
        ...