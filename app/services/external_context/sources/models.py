from __future__ import annotations

from typing import Optional

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
    total_max_pages: Optional[int]
    recursion_depth: Optional[int]
    enable: bool


class APISourceResponse(BaseModel):
    """API response model for external sources."""

    id: str
    name: str
    type_id: str
    category_id: str
    url: str
    description: str
    include_path_patterns: Optional[str]
    exclude_path_patterns: Optional[str]
    total_max_pages: Optional[int]
    recursion_depth: Optional[int]
    enabled: bool
    source_type_ref: dict
    category_ref: dict


class APIResponse(BaseModel):
    """Root API response model."""

    items: list[APISourceResponse]
    total: int
    page: int
    page_size: int
