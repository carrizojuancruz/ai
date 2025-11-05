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
            enabled=api_source.enabled
        )

    async def get_all(self) -> List[ExternalSource]:
        """Get all sources from external API with pagination support."""
        endpoint = "/internal/kb-sources"
        all_sources = []
        page = 1

        while True:
            params = {"page": page}
            response_data = await self.client.get(endpoint, params)

            if response_data is None:
                raise ConnectionError("Failed to connect to external sources API")

            if not response_data:
                logger.warning("No data received from external sources API")
                break

            try:
                api_response = APIResponse(**response_data)

                page_sources = [
                    self._map_api_to_external_source(api_source)
                    for api_source in api_response.items
                ]
                all_sources.extend(page_sources)

                logger.debug(f"Retrieved page {page} with {len(page_sources)} sources "
                           f"(total so far: {len(all_sources)}/{api_response.total})")

                if len(api_response.items) == 0 or len(all_sources) >= api_response.total:
                    break

                page += 1

            except Exception as e:
                logger.error(f"Error processing external API response for page {page}: {e}")
                raise e

        logger.info(f"Retrieved {len(all_sources)} total sources from external API across {page} pages")
        return all_sources
