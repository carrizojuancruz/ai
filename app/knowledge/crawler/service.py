import logging
import ssl
import warnings
from typing import Any, Dict, List

from bs4 import XMLParsedAsHTMLWarning
from langchain_community.document_loaders import RecursiveUrlLoader, SitemapLoader
from langchain_core.documents import Document

from app.core.config import config
from app.knowledge.models import Source
from .content_utils import ContentProcessor, UrlFilter

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

logger = logging.getLogger(__name__)


class CrawlerService:
    """Web crawler service with advanced filtering and content extraction."""

    def __init__(self):
        """Initialize the crawler service with configuration."""
        self._config = config
        self.crawl_type = config.CRAWL_TYPE
        self.timeout = config.CRAWL_TIMEOUT

        ssl._create_default_https_context = ssl._create_unverified_context

    def _filter_documents(self, documents: List[Document]) -> List[Document]:
        """Filter out unwanted documents based on URL patterns."""
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

    async def crawl_source(self, source: Source) -> Dict[str, Any]:
        try:
            documents = await self._load_documents(source)

            result = {
                "documents": documents,
                "documents_loaded": len(documents),
                "source_url": source.url,
                "message": f"Successfully loaded {len(documents)} documents",
                "crawl_type": self.crawl_type
            }

            logger.debug(f"Crawl completed for {source.url}: {len(documents)} documents loaded")
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
            return await self._load_single_page(source.url)
        elif crawl_type == "sitemap":
            return await self._load_sitemap(source.url, source.total_max_pages)
        else:
            return await self._load_recursive(source, source.total_max_pages, source.recursion_depth)

    def _create_loader(self, url: str, loader_type: str, **kwargs):
        """Create appropriate loader based on type."""
        headers = ContentProcessor.get_headers()
        
        if loader_type == "recursive":
            return RecursiveUrlLoader(
                url=url,
                max_depth=kwargs.get('max_depth', 0),
                prevent_outside=kwargs.get('prevent_outside', True),
                timeout=self.timeout,
                exclude_dirs=kwargs.get('exclude_dirs', []),
                extractor=ContentProcessor.extract_clean_text,
                check_response_status=False,
                continue_on_failure=True,
                headers=headers,
                ssl=False
            )
        elif loader_type == "sitemap":
            return SitemapLoader(
                web_path=url,
                filter_urls=kwargs.get('filter_urls')
            )

    async def _load_recursive(self, source: Source, max_pages: int, max_depth: int) -> List[Document]:
        """Load documents recursively from a source."""
        try:
            exclude_dirs = UrlFilter.build_exclude_dirs(source)
            max_docs_to_crawl = min(max_pages, config.MAX_DOCUMENTS_PER_SOURCE)
            
            loader = self._create_loader(
                source.url,
                "recursive",
                max_depth=max_depth,
                exclude_dirs=exclude_dirs
            )

            documents = loader.load()[:max_docs_to_crawl]
            return self._filter_documents(documents)

        except Exception as e:
            logger.error(f"Recursive load error for {source.url}: {e}")
            return []

    async def _load_sitemap(self, url: str, max_pages: int) -> List[Document]:
        """Load documents from sitemap."""
        try:
            def sitemap_filter(url: str) -> bool:
                return not UrlFilter.should_exclude_url(url)

            loader = self._create_loader(url, "sitemap", filter_urls=sitemap_filter)
            documents = loader.load()[:max_pages]
            return documents

        except Exception as e:
            logger.error(f"Sitemap load error for {url}: {e}")
            return []

    async def _load_single_page(self, url: str) -> List[Document]:
        """Load a single page."""
        try:
            loader = self._create_loader(url, "recursive", max_depth=0)
            return loader.load()

        except Exception as e:
            logger.error(f"Single page load error for {url}: {e}")
            return []
