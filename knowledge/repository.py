import json
import os
from pathlib import Path
from typing import List

from .models import Source


class SourceRepository:

    def __init__(self):
        env_path = os.getenv("SOURCES_FILE_PATH")
        self.file_path = str(Path(env_path).resolve())
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
        data = [source.model_dump() for source in sources]
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def find_by_id(self, source_id: str) -> Source | None:
        sources = self.load_all()
        return next((s for s in sources if s.id == source_id), None)

    def find_by_url(self, url: str) -> Source | None:
        sources = self.load_all()
        return next((s for s in sources if s.url == url), None)

    def add(self, source: Source) -> None:
        sources = self.load_all()
        existing = self.find_by_id(source.id)
        if existing:
            self.update(source)
        else:
            sources.append(source)
            self.save_all(sources)

    def update(self, source: Source) -> bool:
        sources = self.load_all()
        for i, s in enumerate(sources):
            if s.id == source.id:
                sources[i] = source
                self.save_all(sources)
                return True
        return False

    def delete_by_id(self, source_id: str) -> bool:
        sources = self.load_all()
        for i, source in enumerate(sources):
            if source.id == source_id:
                del sources[i]
                self.save_all(sources)
                return True
        return False
