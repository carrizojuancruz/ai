import logging
import ssl
import warnings
from typing import Any, Dict, List

from bs4 import XMLParsedAsHTMLWarning
from langchain_core.documents import Document

from app.core.config import config
from app.knowledge.crawler.content_utils import JavaScriptDetector, UrlFilter
from app.knowledge.crawler.loaders.pdf_loader import PDFLoader
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
        return [doc for doc in documents
                if not (hasattr(doc, 'metadata') and 'source' in doc.metadata and
                       UrlFilter.should_exclude_url(doc.metadata['source']))]

    async def crawl_source(self, source: Source) -> Dict[str, Any]:
        try:
            documents = await self._load_documents(source)
            return {
                "documents": documents,
                "documents_loaded": len(documents),
                "source_url": source.url,
                "message": f"Successfully loaded {len(documents)} documents",
                "crawl_type": self.crawl_type
            }
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
        loader = self._get_loader(source, crawl_type)

        try:
            documents = await loader.load_documents()

            if crawl_type == "recursive" and self._has_corrupted_content(documents):
                logger.warning(f"Detected corrupted content from recursive crawl for {source.url}, falling back to single page loader")
                documents = await SinglePageLoader(source=source).load_documents()

            elif crawl_type != "single" and not source.url.lower().endswith('.pdf') and JavaScriptDetector.needs_javascript(documents):
                documents = await SinglePageLoader(source=source).load_documents()

            return self._filter_documents(documents)
        except Exception as e:
            logger.error(f"Load error for {source.url}: {e}")
            if crawl_type != "single" and not source.url.lower().endswith('.pdf'):
                try:
                    documents = await SinglePageLoader(source=source).load_documents()
                    return self._filter_documents(documents)
                except Exception:
                    pass
            return []

    def _has_corrupted_content(self, documents: List[Document]) -> bool:
        """Check if any document contains corrupted binary content."""
        for doc in documents:
            content = doc.page_content
            if not content or len(content) < 10:
                continue
            sample = content[:100]
            corrupted_chars = [c for c in sample if ord(c) > 127 or ord(c) < 32 and ord(c) not in [9, 10, 13]]
            if corrupted_chars:
                return True
        return False

    def _get_loader(self, source: Source, crawl_type: str):
        if source.url.lower().endswith('.pdf'):
            return PDFLoader(source=source)
        elif crawl_type == "single":
            return SinglePageLoader(source=source)
        elif crawl_type == "sitemap":
            return SitemapLoader(source=source, max_pages=source.total_max_pages)
        else:
            logger.info(f"Using recursive loader for {source.url} with max_pages={source.total_max_pages} and recursion_depth={source.recursion_depth}")
            return RecursiveLoader(source=source, max_pages=source.total_max_pages,
                                 max_depth=source.recursion_depth)
