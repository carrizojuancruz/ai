from __future__ import annotations

import logging
from typing import List

from .interface import ExternalSourcesRepositoryInterface
from .models import APIResponse, ExternalSource

logger = logging.getLogger(__name__)


class ExternalSourcesRepository(ExternalSourcesRepositoryInterface):
    """Repository for external sources operations."""

    def __init__(self) -> None:
        pass

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
        """Get all sources from external API - MOCKED implementation."""
        mock_data = {
            "items": [
                {
                    "id": "84e5cf18-d59e-472c-8b2d-e959fb97e605",
                    "name": "211.org",
                    "type_id": "747fae55-bd8c-435d-a8a5-e52e9a366b04",
                    "category_id": "d140a0db-66b4-46fb-8813-5d3ada849017",
                    "url": "http://211.org",
                    "description": "Information and referrals for social services",
                    "include_path_patterns": None,
                    "exclude_path_patterns": None,
                    "total_max_pages": None,
                    "recursion_depth": None,
                    "enabled": True,
                    "meta_data": {},
                    "created_by": "ba5c5db4-d3fb-4ca8-9445-1c221ea502a8",
                    "updated_by": "ba5c5db4-d3fb-4ca8-9445-1c221ea502a8",
                    "created_at": "2025-08-31T22:05:30.141437Z",
                    "updated_at": "2025-08-31T22:05:30.141437Z",
                    "source_type_ref": {
                        "name": "Information Service",
                        "id": "747fae55-bd8c-435d-a8a5-e52e9a366b04",
                        "created_at": "2025-08-31T22:05:30.141437Z",
                        "updated_at": "2025-08-31T22:05:30.141437Z"
                    },
                    "category_ref": {
                        "name": "Personal Finance",
                        "id": "d140a0db-66b4-46fb-8813-5d3ada849017",
                        "created_at": "2025-08-31T18:27:06.867504Z",
                        "updated_at": "2025-08-31T18:27:06.867504Z"
                    }
                }
            ]
        }

        try:
            api_response = APIResponse(**mock_data)
            external_sources = [
                self._map_api_to_external_source(api_source)
                for api_source in api_response.items
            ]

            logger.info(f"Returning {len(external_sources)} mock sources")
            return external_sources

        except Exception as e:
            logger.error(f"Error processing mock data: {e}")
            return []
