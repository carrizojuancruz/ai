from __future__ import annotations
import logging
import os
from typing import Any, Dict
from app.core.config import config
import httpx

logger = logging.getLogger(__name__)


class FOSHttpClient:
    """HTTP client for FOS service."""

    def __init__(self):
        self.base_url = (config.FOS_SERVICE_URL).rstrip('/')
        self.api_key = config.FOS_API_KEY

        if not self.base_url:
            logger.info("FOS_SERVICE_URL not set; FOS API calls will be skipped")

    def _build_headers(self) -> Dict[str, str]:
        """Build request headers with API key."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    async def get(self, endpoint: str) -> Dict[str, Any] | None:
        """GET request to FOS service."""
        if not self.base_url:
            return None

        url = f"{self.base_url}{endpoint}"
        headers = self._build_headers()

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning(f"FOS API GET failed for {endpoint}: {e}")
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

    async def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any] | None:
        """POST request to FOS service."""
        if not self.base_url:
            return None

        url = f"{self.base_url}{endpoint}"
        headers = self._build_headers()

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, headers=headers, json=data)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning(f"FOS API POST failed for {endpoint}: {e}")
            return None
