from __future__ import annotations

import logging
from typing import List

from app.services.external_context.http_client import FOSHttpClient

from .interface import ExternalSourcesRepositoryInterface
from .models import APIResponse, ExternalSource

logger = logging.getLogger(__name__)


class ExternalSourcesRepository(ExternalSourcesRepositoryInterface):
    """Repository for external sources operations."""

    def __init__(self) -> None:
        self.client = FOSHttpClient()

    def _map_api_to_external_source(self, api_source) -> ExternalSource:
        """Map API response to ExternalSource model."""
        return ExternalSource(
            name=api_source.name,
            type=api_source.source_type_ref.get("name", ""),
            category=api_source.category_ref.get("name", ""),
            url=api_source.url,
            description=api_source.description or "",
            include_path_patterns=api_source.include_path_patterns or "",
            exclude_path_patterns=api_source.exclude_path_patterns or "",
            total_max_pages=api_source.total_max_pages,
            recursion_depth=api_source.recursion_depth,
            enable=api_source.enabled
        )

    async def get_all(self) -> List[ExternalSource]:
        """Get all sources from external API."""
        endpoint = "/internal/kb-sources"

        try:
            response_data = await self.client.get(endpoint)
            if not response_data:
                logger.warning("No data received from external sources API")
                return []

            api_response = APIResponse(**response_data)
            external_sources = [
                self._map_api_to_external_source(api_source)
                for api_source in api_response.items[:10]
            ]

            logger.info(f"Retrieved {len(external_sources)} sources from external API")
            return external_sources

        except Exception as e:
            logger.error(f"Error processing external API response: {e}")
            return []
