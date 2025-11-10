from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class Source(BaseModel):
    """Source entity for knowledge base."""

    id: str
    name: str
    url: str
    enabled: bool = True
    type: str | None = None
    category: str | None = None
    description: str | None = None
    include_path_patterns: str | None = None
    exclude_path_patterns: str | None = None
    total_max_pages: int | None = None
    recursion_depth: int | None = None
    last_sync: datetime | None = None
    total_chunks: int = 0
    section_urls: Optional[List[str]] = None
    content_source: str = "external"
