import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import List, Optional

from app.core.config import config as appConfig
from app.knowledge.models import Source
from app.knowledge.sources.base_repository import SourceRepositoryInterface


class SourceRepository(SourceRepositoryInterface):
    """JSON file-based implementation of SourceRepositoryInterface."""

    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path or str(Path(appConfig.SOURCES_FILE_PATH).resolve())
        self._ensure_file_exists()

    def load_all(self) -> List[Source]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [Source(**source) for source in data]
        except Exception:
            return []

    def _ensure_file_exists(self) -> None:
        if not os.path.exists(self.file_path):
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2, ensure_ascii=False)

    def save_all(self, sources: List[Source]) -> None:
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        data = [source.model_dump(mode='json') for source in sources]
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def find_by_id(self, source_id: str) -> Optional[Source]:
        sources = self.load_all()
        return next((s for s in sources if s.id == source_id), None)

    def find_by_url(self, url: str) -> Optional[Source]:
        sources = self.load_all()
        return next((s for s in sources if s.url == url), None)

    def add(self, source: Source) -> None:
        sources = self.load_all()
        sources.append(source)
        self.save_all(sources)

    def update(self, source: Source) -> bool:
        sources = self.load_all()
        for i, s in enumerate(sources):
            if s.url == source.url:
                sources[i] = source
                self.save_all(sources)
                return True
        return False

    def upsert(self, source: Source) -> None:
        """Insert or update a source."""
        source.last_sync = datetime.now(UTC).replace(microsecond=0)

        existing = self.find_by_url(source.url)
        if existing:
            self.update(source)
        else:
            self.add(source)

    def delete_by_url(self, url: str) -> bool:
        sources = self.load_all()
        for i, source in enumerate(sources):
            if source.url == url:
                del sources[i]
                self.save_all(sources)
                return True
        return False

    def delete_all(self) -> bool:
        """Delete all sources from the repository."""
        try:
            self.save_all([])
            return True
        except Exception:
            return False
