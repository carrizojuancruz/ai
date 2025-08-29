"""External sources repository with mocked implementation."""

from __future__ import annotations

import logging
from typing import List

from .interface import ExternalSourcesRepositoryInterface
from .models import ExternalSource

logger = logging.getLogger(__name__)


class ExternalSourcesRepository(ExternalSourcesRepositoryInterface):
    """Repository for external sources operations - MOCKED for now."""

    def __init__(self) -> None:
        logger.info("ExternalSourcesRepository initialized with MOCK data")

    async def get_all(self) -> List[ExternalSource]:
        """Get all sources from external API - MOCKED implementation."""
        mock_sources = [
            ExternalSource(
                name="Tienda verde",
                type="Technology Website",
                category="AI/Tech",
                url="https://verdemoney.com/es/",
                description="AI prompting and automation platform",
                include_path_patterns="",
                exclude_path_patterns="",
                total_max_pages=30,
                recursion_depth=2,
                enable=True
            )
        ]

        logger.info(f"Returning {len(mock_sources)} mock sources")
        return mock_sources
