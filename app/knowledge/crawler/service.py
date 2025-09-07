import logging
import ssl
import warnings
from typing import Any, Dict, List

from bs4 import XMLParsedAsHTMLWarning
from langchain_core.documents import Document

from app.core.config import config
from app.knowledge.crawler.content_utils import PlaceholderDetector, UrlFilter
from app.knowledge.crawler.loaders.playwright_loader import PlaywrightLoader
from app.knowledge.crawler.loaders.recursive_loader import RecursiveLoader
from app.knowledge.crawler.loaders.single_page_loader import SinglePageLoader
from app.knowledge.crawler.loaders.sitemap_loader import SitemapLoader
from app.knowledge.models import Source

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

logger = logging.getLogger(__name__)


class CrawlerService:

    def __init__(self):
        self._config = config
        self.crawl_type = config.CRAWL_TYPE
        ssl._create_default_https_context = ssl._create_unverified_context

    def _filter_documents(self, documents: List[Document]) -> List[Document]:
        filtered_documents = []

        for doc in documents:
            if not hasattr(doc, 'metadata') or 'source' not in doc.metadata:
                filtered_documents.append(doc)
                continue

            source_url = doc.metadata['source']
            if UrlFilter.should_exclude_url(source_url):
                logger.debug(f"Filtered out asset URL: {source_url}")
                continue

            filtered_documents.append(doc)

        return filtered_documents

    def _is_content_blocked(self, document: Document) -> bool:
        if not document or not document.page_content:
            return True

        return PlaceholderDetector.is_blocked_content(document.page_content)

    async def _try_playwright_fallback(self, source: Source) -> List[Document]:
        try:
            logger.info(f"Trying Playwright fallback for {source.url}")
            playwright_loader = PlaywrightLoader(source=source)
            documents = await playwright_loader.load_documents()
            return self._filter_documents(documents)
        except Exception as e:
            logger.error(f"Playwright fallback failed for {source.url}: {e}")
            return []

    async def crawl_source(self, source: Source) -> Dict[str, Any]:
        try:
            documents = await self._load_documents(source)
            filtered_documents = self._filter_documents(documents)

            result = {
                "documents": filtered_documents,
                "documents_loaded": len(filtered_documents),
                "source_url": source.url,
                "message": f"Successfully loaded {len(filtered_documents)} documents",
                "crawl_type": self.crawl_type
            }

            return result

        except Exception as e:
            logger.error(f"Error crawling source {source.url}: {e}")
            return {
                "documents": [],
                "documents_loaded": 0,
                "source_url": source.url,
                "message": f"Failed to crawl source: {str(e)}",
                "error": str(e)
            }

    async def _load_documents(self, source: Source) -> List[Document]:
        crawl_type = self.crawl_type.lower()

        if crawl_type == "single":
            loader = SinglePageLoader(source=source)
        elif crawl_type == "sitemap":
            loader = SitemapLoader(source=source, max_pages=source.total_max_pages)
        else:
            loader = RecursiveLoader(
                source=source,
                max_pages=source.total_max_pages,
                max_depth=source.recursion_depth
            )

        try:
            documents = await loader.load_documents()
            filtered_docs = self._filter_documents(documents)

            if filtered_docs and not self._is_content_blocked(filtered_docs[0]):
                return filtered_docs

        except Exception as e:
            logger.error(f"Load error for {source.url}: {e}")

        return await self._try_playwright_fallback(source)
