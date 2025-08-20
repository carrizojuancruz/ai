import json
import os
from typing import List

from .models import Source


class SourceRepository:
    
    def __init__(self, file_path: str = "knowledge/sources.json"):
        self.file_path = file_path
    
    def load_all(self) -> List[Source]:
        if not os.path.exists(self.file_path):
            return []
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [Source(**source) for source in data]
        except Exception:
            return []
    
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
