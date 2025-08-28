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
                name="Verde Money",
                type="Financial Website",
                category="Finance",
                url="https://verdemoney.com/es/",
                description="Plataforma financiera Verde Money",
                include_path_patterns="",
                exclude_path_patterns="",
                total_max_pages="30",
                recursion_depth="2",
                enable="true"
            ),
            ExternalSource(
                name="Tienda Inglesa",
                type="E-commerce",
                category="Retail",
                url="https://www.tiendainglesa.com.uy/",
                description="Supermercado online Tienda Inglesa Uruguay",
                include_path_patterns="",
                exclude_path_patterns="",
                total_max_pages="20",
                recursion_depth="1",
                enable="true"
            )
        ]

        logger.info(f"Returning {len(mock_sources)} mock sources")
        return mock_sources
