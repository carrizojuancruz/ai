import logging
from abc import ABC, abstractmethod
from typing import Dict, List

from langchain_core.documents import Document

from app.knowledge.crawler.content_utils import ContentProcessor
from app.knowledge.models import Source

logger = logging.getLogger(__name__)


class BaseLoader(ABC):

    def __init__(self, source: Source, **kwargs):
        self.source = source
        self.kwargs = kwargs

    @abstractmethod
    async def load_documents(self) -> List[Document]:
        pass

    def clean_content(self, html_content: str) -> str:
        return ContentProcessor.extract_clean_text(html_content)

    def create_document(self, content: str, url: str, loader_name: str, **extra_metadata) -> Document:
        metadata = {
            "source": url,
            "loader": loader_name,
            "url": url,
            "source_id": self.source.id,
            **extra_metadata
        }
        return Document(page_content=content, metadata=metadata)

    def get_headers(self) -> Dict[str, str]:
        return ContentProcessor.get_headers()
