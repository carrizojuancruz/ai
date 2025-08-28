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
        logger.info("Fetching sources from MOCK data (not real external API)")

        mock_sources = [
            ExternalSource(
                name="MyMoney.gov",
                type="Government Portal",
                category="Personal Finance",
                url="https://mymoney.gov",
                description="Official U.S. government portal for financial education programs and information",
                include_path_patterns="",
                exclude_path_patterns="",
                total_max_pages="1",
                recursion_depth="2",
                enable="true"
            ),
            ExternalSource(
                name="Consumer Finance Protection Bureau",
                type="Government Agency",
                category="Consumer Protection",
                url="https://consumerfinance.gov",
                description="Federal agency helping consumers with financial products and services",
                include_path_patterns="",
                exclude_path_patterns="",
                total_max_pages="1",
                recursion_depth="2",
                enable="true"
            ),
            ExternalSource(
                name="National Endowment for Financial Education",
                type="Non-Profit Organization",
                category="Financial Education",
                url="https://nefe.org",
                description="Educational resources for personal finance and financial literacy",
                include_path_patterns="",
                exclude_path_patterns="",
                total_max_pages="1",
                recursion_depth="2",
                enable="true"
            )
        ]

        logger.info(f"Returning {len(mock_sources)} mock sources")
        return mock_sources
