"""Models for external sources data."""

from __future__ import annotations

from pydantic import BaseModel


class ExternalSource(BaseModel):
    """External source data model matching the external API response."""

    name: str
    type: str
    category: str
    url: str
    description: str
    include_path_patterns: str
    exclude_path_patterns: str
    total_max_pages: int
    recursion_depth: int
    enable: bool
