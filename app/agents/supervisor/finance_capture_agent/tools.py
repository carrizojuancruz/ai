from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.app_state import get_cached_taxonomy, set_cached_taxonomy
from app.services.external_context.http_client import FOSHttpClient

logger = logging.getLogger(__name__)


class TaxonomyItem(BaseModel):
    """Single taxonomy item from FOS API - represents a category+subcategory combination."""

    id: str
    primary: str
    primary_display: str
    detailed: str
    detailed_display: str
    description: str | None = None


class TaxonomyResult(BaseModel):
    scope: Literal["income", "expenses", "primaries", "grouped"]
    categories: list[TaxonomyItem] = Field(default_factory=list)
    total: int = 0


class PersistResponse(BaseModel):
    status_code: int
    body: dict[str, Any] | None = None


def _ensure_client(client: FOSHttpClient | None) -> FOSHttpClient:
    return client or FOSHttpClient()


async def get_taxonomy(
    scope: Literal["income", "expenses", "primaries", "grouped"],
    *,
    client: FOSHttpClient | None = None,
) -> TaxonomyResult:
    cached_data = get_cached_taxonomy(scope)
    if cached_data is not None:
        logger.info("[finance_capture] get_taxonomy scope=%s (cached)", scope)
        return TaxonomyResult.model_validate(cached_data)

    fos_client = _ensure_client(client)
    endpoint = f"/internal/financial/taxonomy/{scope}"
    logger.info("[finance_capture] get_taxonomy scope=%s (fetching)", scope)
    response = await fos_client.get(endpoint=endpoint)
    if response is None:
        raise RuntimeError(f"Failed to fetch taxonomy for scope={scope}")

    raw_items: list[dict[str, Any]] = []
    total = 0

    if isinstance(response, Mapping):
        raw_items = response.get("categories") or []
        total = response.get("total", len(raw_items))
    elif isinstance(response, list):
        raw_items = response
        total = len(response)

    categories: list[TaxonomyItem] = []
    for item in raw_items:
        if not isinstance(item, Mapping):
            continue
        try:
            taxonomy_item = TaxonomyItem(
                id=str(item.get("id", "")),
                primary=str(item.get("primary", "")),
                primary_display=str(item.get("primary_display", "")),
                detailed=str(item.get("detailed", "")),
                detailed_display=str(item.get("detailed_display", "")),
                description=item.get("description"),
            )
            if taxonomy_item.id:
                categories.append(taxonomy_item)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[finance_capture] taxonomy_item_parse_failed item=%s error=%s", item, exc)
            continue

    result = TaxonomyResult(scope=scope, categories=categories, total=total)

    set_cached_taxonomy(scope, result.model_dump())

    return result


async def persist_asset(
    *,
    user_id: str,
    payload: Mapping[str, Any],
    client: FOSHttpClient | None = None,
) -> PersistResponse:
    fos_client = _ensure_client(client)
    endpoint = f"/internal/assets/user/{user_id}"
    logger.info("[finance_capture] persist_asset user_id=%s", user_id)
    response = await fos_client.post(endpoint=endpoint, data=dict(payload))
    if response is None:
        return PersistResponse(status_code=200, body=None)
    if isinstance(response, Mapping):
        return PersistResponse(status_code=200, body=dict(response))
    return PersistResponse(status_code=200, body=None)


async def persist_liability(
    *,
    user_id: str,
    payload: Mapping[str, Any],
    client: FOSHttpClient | None = None,
) -> PersistResponse:
    fos_client = _ensure_client(client)
    endpoint = f"/internal/liabilities/user/{user_id}"
    logger.info("[finance_capture] persist_liability user_id=%s", user_id)
    response = await fos_client.post(endpoint=endpoint, data=dict(payload))
    if response is None:
        return PersistResponse(status_code=200, body=None)
    if isinstance(response, Mapping):
        return PersistResponse(status_code=200, body=dict(response))
    return PersistResponse(status_code=200, body=None)


async def persist_manual_transaction(
    *,
    user_id: str,
    payload: Mapping[str, Any],
    client: FOSHttpClient | None = None,
) -> PersistResponse:
    fos_client = _ensure_client(client)
    endpoint = f"/internal/financial/transactions/manual/{user_id}"
    logger.info("[finance_capture] persist_manual_transaction user_id=%s", user_id)
    response = await fos_client.post(endpoint=endpoint, data=dict(payload))
    if response is None:
        return PersistResponse(status_code=200, body=None)
    if isinstance(response, Mapping):
        return PersistResponse(status_code=200, body=dict(response))
    return PersistResponse(status_code=200, body=None)


