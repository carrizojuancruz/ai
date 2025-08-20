import logging
from typing import List
import requests
from bs4 import BeautifulSoup
from langchain_community.document_loaders import RecursiveUrlLoader, SitemapLoader
from langchain_core.documents import Document
from app.knowledge import config

logger = logging.getLogger(__name__)

class CrawlConfig:
    def __init__(self, url: str, crawl_type: str = None, max_depth: int = None, max_pages: int = None, timeout: int = None):
        self.url = url
        self.crawl_type = crawl_type or config.CRAWL_TYPE
        self.max_depth = max_depth or config.CRAWL_MAX_DEPTH
        self.max_pages = max_pages or config.CRAWL_MAX_PAGES
        self.timeout = timeout or config.CRAWL_TIMEOUT

class WebLoader:

    async def load_sitemap(self, config: CrawlConfig) -> List[Document]:
        try:
            loader = SitemapLoader(web_path=str(config.url))
            documents = loader.load()
            documents = self._limit_documents(documents, config.max_pages)
            documents = self._clean_documents(documents)
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
                timeout=config.timeout
            )
            documents = loader.load()
            documents = self._limit_documents(documents, config.max_pages)
            documents = self._clean_documents(documents)
            return self._add_metadata(documents, str(config.url))
        except Exception as e:
            logger.error(f"Recursive load error for {config.url}: {e}")
            return []

    def _limit_documents(self, documents: List[Document], max_pages: int) -> List[Document]:
        if len(documents) > max_pages:
            return documents[:max_pages]
        return documents

    def _clean_html_content(self, html_content: str) -> str:
        soup = BeautifulSoup(html_content, "html.parser")
        
        for tag in soup(["script", "style", "noscript", "meta", "link", "head", "nav", "header", "footer"]):
            tag.decompose()
        
        text = soup.get_text(separator=" ", strip=True)
        return ' '.join(text.split())

    def _clean_documents(self, documents: List[Document]) -> List[Document]:
        for doc in documents:
            doc.page_content = self._clean_html_content(doc.page_content)
        return documents

    def _add_metadata(self, documents: List[Document], source_url: str) -> List[Document]:
        for doc in documents:
            if "source" not in doc.metadata:
                doc.metadata["source"] = source_url
        return documents

    def load_html(self, url: str, timeout: int) -> str:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return self._clean_html_content(response.text)

    async def load_single_page(self, config: CrawlConfig) -> List[Document]:
        try:
            html_text = self.load_html(str(config.url), config.timeout)
            documents = [Document(page_content=html_text)]
            return self._add_metadata(documents, str(config.url))
        except Exception as e:
            logger.error(f"Single page load error for {config.url}: {e}")
            return []

