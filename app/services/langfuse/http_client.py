"""HTTP client for Langfuse API communication."""

import logging
from datetime import datetime
from typing import List

import httpx

TRACES_API_LIMIT = 100
HTTP_TIMEOUT = 30

logger = logging.getLogger(__name__)


class LangfuseHttpClient:
    """Handles HTTP communication with Langfuse API."""

    def __init__(self, public_key: str, secret_key: str, base_url: str):
        self.public_key = public_key
        self.secret_key = secret_key
        self.base_url = base_url

    def get_traces(self, start_time: datetime, end_time: datetime) -> List[dict]:
        """Fetch traces from Langfuse API."""
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.base_url}/api/public/traces",
                    auth=(self.public_key, self.secret_key),
                    params={
                        "fromTimestamp": start_time.isoformat() + "Z",
                        "toTimestamp": end_time.isoformat() + "Z",
                        "limit": TRACES_API_LIMIT
                    },
                    timeout=HTTP_TIMEOUT
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get('data', [])
                else:
                    logger.warning(f"Langfuse API returned status {response.status_code}")

        except httpx.RequestError as e:
            logger.error(f"HTTP request failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching traces: {e}")

        return []
