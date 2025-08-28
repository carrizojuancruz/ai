from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional
from uuid import UUID

from app.core.config import config

logger = logging.getLogger(__name__)


class ExternalUserRepository:
    def __init__(self) -> None:
        self.base_url: str | None = config.FOS_SERVICE_URL
        self.api_key: Optional[str] = config.FOS_API_KEY

        if not self.base_url:
            logger.info("FOS_SERVICE_URL not set; Context prefill will be skipped during initialization")

    async def get_by_id(self, user_id: UUID) -> dict[str, Any] | None:
        if not self.base_url:
            return None

        url = f"{self.base_url.rstrip('/')}/internal/ai/context/{user_id}"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        try:
            try:
                import httpx

                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code == 404:
                        return None
                    resp.raise_for_status()
                    return resp.json()
            except ModuleNotFoundError:
                import urllib.error
                import urllib.request

                def _sync_get() -> dict[str, Any] | None:
                    request = urllib.request.Request(url, headers=headers, method="GET")
                    try:
                        with urllib.request.urlopen(request, timeout=5.0) as resp:
                            status = resp.getcode()
                            if status == 404:
                                return None
                            data = resp.read().decode("utf-8")
                            return json.loads(data)
                    except urllib.error.HTTPError as e:
                        if e.code == 404:
                            return None
                        logger.warning("FOS API HTTP error: %s", e)
                        return None
                    except Exception as e:
                        logger.warning("FOS API request failed: %s", e)
                        return None

                return await asyncio.to_thread(_sync_get)
        except Exception as e:
            logger.warning("FOS API fetch failed: %s", e)
            return None

    async def upsert(self, user_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        if not self.base_url:
            return None

        url = f"{self.base_url.rstrip('/')}/internal/ai/context/{user_id}"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        try:
            try:
                import httpx

                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.put(url, headers=headers, json=data)
                    if resp.status_code == 404:
                        return None
                    resp.raise_for_status()
                    return resp.json()
            except ModuleNotFoundError:
                import urllib.error
                import urllib.request

                def _sync_put() -> dict[str, Any] | None:
                    body = json.dumps(data).encode("utf-8")
                    request = urllib.request.Request(url, headers=headers, method="PUT", data=body)
                    try:
                        with urllib.request.urlopen(request, timeout=8.0) as resp:
                            status = resp.getcode()
                            if status == 404:
                                return None
                            raw = resp.read().decode("utf-8")
                            return json.loads(raw) if raw else {}
                    except urllib.error.HTTPError as e:
                        if e.code == 404:
                            return None
                        logger.warning("FOS API PUT error: %s", e)
                        return None
                    except Exception as e:
                        logger.warning("FOS API PUT failed: %s", e)
                        return None

                return await asyncio.to_thread(_sync_put)
        except Exception as e:
            logger.warning("FOS API put failed: %s", e)
            return None
