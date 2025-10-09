from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

from app.core.config import config

logger = logging.getLogger(__name__)


class FOSHttpClient:
    """HTTP client for FOS service."""

    def __init__(self):
        self.base_url = (config.FOS_SERVICE_URL).rstrip('/') if config.FOS_SERVICE_URL else None
        self.api_key = config.FOS_API_KEY

    def _build_headers(self) -> Dict[str, str]:
        """Build request headers with API key."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    async def get(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any] | None:
        """GET request to FOS service."""
        if not self.base_url:
            logger.warning("FOS_SERVICE_URL not configured - skipping external API call")
            return None

        url = f"{self.base_url}{endpoint}"
        headers = self._build_headers()

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                logger.debug(f"Calling FOS API: {url}" + (f" with params: {params}" if params else ""))
                resp = await client.get(url, headers=headers, params=params)
                if resp.status_code == 404:
                    logger.warning(f"FOS API endpoint not found: {endpoint}")
                    return None
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"FOS API HTTP error for {endpoint}: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"FOS API connection failed for {endpoint}: {type(e).__name__}: {e}")
            return None

    async def put(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any] | None:
        """PUT request to FOS service."""
        if not self.base_url:
            return None

        url = f"{self.base_url}{endpoint}"
        headers = self._build_headers()

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.put(url, headers=headers, json=data)
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning(f"FOS API PUT failed for {endpoint}: {e}")
            return None

    async def patch(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any] | None:
        """PATCH request to FOS service."""
        if not self.base_url:
            return None

        url = f"{self.base_url}{endpoint}"
        headers = self._build_headers()

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.patch(url, headers=headers, json=data)
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning(f"FOS API PATCH failed for {endpoint}: {e}")
            return None

    async def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any] | None:
        """POST request to FOS service."""
        if not self.base_url:
            return None

        url = f"{self.base_url}{endpoint}"
        headers = self._build_headers()

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, headers=headers, json=data)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"FOS API POST failed for {endpoint}: Client error '{e.response.status_code} {e.response.reason_phrase}' for url '{e.request.url}'")
            return None
        except Exception as e:
            logger.warning(f"FOS API POST failed for {endpoint}: {type(e).__name__}: {e}")
            return None

    async def delete(self, endpoint: str) -> Dict[str, Any] | None:
        """DELETE request to FOS service."""
        if not self.base_url:
            return None

        url = f"{self.base_url}{endpoint}"
        headers = self._build_headers()

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.delete(url, headers=headers)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning(f"FOS API DELETE failed for {endpoint}: {e}")
            return None
