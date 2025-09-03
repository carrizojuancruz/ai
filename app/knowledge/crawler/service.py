import logging
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup
from langchain_community.document_loaders import RecursiveUrlLoader, SitemapLoader
from langchain_core.documents import Document

from app.core.config import config
from app.knowledge.models import Source

logger = logging.getLogger(__name__)


class CrawlerService:

    crawl_type = config.CRAWL_TYPE
    max_pages = config.CRAWL_MAX_PAGES
    max_depth = config.CRAWL_MAX_DEPTH
    timeout = config.CRAWL_TIMEOUT

    async def crawl_source(self, source: Source) -> Dict[str, Any]:
        """Crawl a source using its configuration."""
        documents = await self._load_documents(source)

        return {
            "documents": documents,
            "documents_loaded": len(documents),
            "source_url": source.url,
            "message": f"Successfully loaded {len(documents)} documents"
        }

    async def _load_documents(self, source: Source) -> List[Document]:
        """Load documents based on crawl type configuration."""
        max_pages = int(source.total_max_pages or self.max_pages)
        max_depth = int(source.recursion_depth or self.max_depth)

        if self.crawl_type == "single":
            return await self._load_single_page(source.url)
        elif self.crawl_type == "sitemap":
            return await self._load_sitemap(source.url, max_pages)
        else:
            return await self._load_recursive(source, max_pages, max_depth)

    async def _load_sitemap(self, url: str, max_pages: int) -> List[Document]:
        """Load documents from sitemap."""
        try:
            loader = SitemapLoader(web_path=url)
            documents = loader.load()[:max_pages]
            return self._process_documents(documents, url)
        except Exception as e:
            logger.error(f"Sitemap load error for {url}: {e}")
            return []

    async def _load_recursive(self, source: Source, max_pages: int, max_depth: int) -> List[Document]:
        """Load documents recursively following links."""
        try:
            loader = RecursiveUrlLoader(
                url=source.url,
                max_depth=max_depth,
                prevent_outside=True,
                timeout=self.timeout
            )
            documents = loader.load()
            limited_documents = documents[:max_pages]
            return self._process_documents(limited_documents, source.url)
        except Exception as e:
            logger.error(f"Recursive load error for {source.url}: {e}")
            return []

    async def _load_single_page(self, url: str) -> List[Document]:
        """Load a single page."""
        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            text = self._clean_html(response.text)
            doc = Document(page_content=text, metadata={"source": url})
            return [doc]
        except Exception as e:
            logger.error(f"Single page load error for {url}: {e}")
            return []

    def _process_documents(self, documents: List[Document], source_url: str) -> List[Document]:
        """Process and clean document content."""
        for doc in documents:
            doc.page_content = self._clean_html(doc.page_content)
        return documents

    def _clean_html(self, html_content: str) -> str:
        """Clean HTML/XML content removing unnecessary tags."""
        soup = BeautifulSoup(html_content, "lxml")
        for tag in soup(["script", "style", "noscript", "meta", "link", "head", "nav", "header", "footer"]):
            tag.decompose()
        return ' '.join(soup.get_text(separator=" ", strip=True).split())
