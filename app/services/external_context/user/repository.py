"""External user repository using shared HTTP client."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.services.external_context.http_client import FOSHttpClient


class ExternalUserRepository:
    """Repository for external user operations using FOS service."""

    def __init__(self) -> None:
        self.client = FOSHttpClient()

    async def get_by_id(self, user_id: UUID) -> dict[str, Any] | None:
        """Get user context by user ID."""
        endpoint = f"/internal/ai/context/{user_id}"
        return await self.client.get(endpoint)

    async def upsert(self, user_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        """Upsert user context data."""
        endpoint = f"/internal/ai/context/{user_id}"
        return await self.client.put(endpoint, data)
