import logging
from typing import List, Optional

from langchain_core.documents import Document
from langchain_community.document_loaders import (
    RecursiveUrlLoader,
    SitemapLoader,
    WebBaseLoader,
)
from pydantic import BaseModel, HttpUrl

logger = logging.getLogger(__name__)


CRAWL_TYPE: str = "recursive"  # "single" | "sitemap" | "recursive"
MAX_DEPTH: int = 1
MAX_PAGES: int = 5


class CrawlConfig(BaseModel):
    url: HttpUrl
    crawl_type: str = CRAWL_TYPE
    max_depth: int = MAX_DEPTH
    max_pages: int = MAX_PAGES


class WebLoader:
    CRAWL_TIMEOUT = 10
    
    async def load_single_page(self, url: str) -> List[Document]:
        try:
            loader = WebBaseLoader(web_paths=[url])
            documents = loader.load()
            return self._add_metadata(documents, url)
        except Exception as e:
            logger.error(f"Single page load error for {url}: {e}")
            return []
    
    async def load_sitemap(self, config: CrawlConfig) -> List[Document]:
        try:
            loader = SitemapLoader(web_path=str(config.url))
            documents = loader.load()
            documents = self._limit_documents(documents, config.max_pages)
            return self._add_metadata(documents, str(config.url))
        except Exception as e:
            logger.error(f"Sitemap load error for {config.url}: {e}")
            return []
    
    async def load_recursive(self, config: CrawlConfig) -> List[Document]:
        try:
            loader = RecursiveUrlLoader(
                url=str(config.url),
                max_depth=config.max_depth,
                prevent_outside=True,
                timeout=self.CRAWL_TIMEOUT
            )
            documents = loader.load()
            documents = self._limit_documents(documents, config.max_pages)
            return self._add_metadata(documents, str(config.url))
        except Exception as e:
            logger.error(f"Recursive load error for {config.url}: {e}")
            return []
    
    def _limit_documents(self, documents: List[Document], max_pages: int) -> List[Document]:
        if len(documents) > max_pages:
            return documents[:max_pages]
        return documents
    
    def _add_metadata(self, documents: List[Document], source_url: str) -> List[Document]:
        for doc in documents:
            if "source" not in doc.metadata:
                doc.metadata["source"] = source_url
        logger.info(f"Loaded {len(documents)} documents from {source_url}")
        return documents
