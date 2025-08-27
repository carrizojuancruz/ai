from abc import ABC, abstractmethod
from typing import List, Optional

from app.knowledge.models import Source


class SourceRepositoryInterface(ABC):
    """Abstract interface for source repositories."""

    @abstractmethod
    def load_all(self) -> List[Source]:
        """Load all sources."""
        pass

    @abstractmethod
    def find_by_id(self, source_id: str) -> Optional[Source]:
        """Find source by ID."""
        pass

    @abstractmethod
    def find_by_url(self, url: str) -> Optional[Source]:
        """Find source by URL."""
        pass

    @abstractmethod
    def add(self, source: Source) -> None:
        """Add a new source."""
        pass

    @abstractmethod
    def update(self, source: Source) -> bool:
        """Update an existing source."""
        pass

    @abstractmethod
    def delete_by_id(self, source_id: str) -> bool:
        """Delete source by ID."""
        pass
