import logging
from typing import List
import requests
from bs4 import BeautifulSoup
from langchain_community.document_loaders import RecursiveUrlLoader, SitemapLoader
from langchain_core.documents import Document
from app.knowledge import config

logger = logging.getLogger(__name__)

class CrawlConfig:
    def __init__(self, url: str):
        self.url = url
        self.crawl_type = config.CRAWL_TYPE
        self.max_depth = config.CRAWL_MAX_DEPTH
        self.max_pages = config.CRAWL_MAX_PAGES
        self.timeout = config.CRAWL_TIMEOUT

class WebLoader:

    async def load_sitemap(self, config: CrawlConfig) -> List[Document]:
        try:
            loader = SitemapLoader(web_path=config.url)
            documents = loader.load()[:config.max_pages]
            return self._process_documents(documents, config.url)
        except Exception as e:
            logger.error(f"Sitemap load error for {config.url}: {e}")
            return []

    async def load_recursive(self, config: CrawlConfig) -> List[Document]:
        try:
            loader = RecursiveUrlLoader(
                url=config.url,
                max_depth=config.max_depth,
                prevent_outside=True,
                timeout=config.timeout
            )
            documents = loader.load()[:config.max_pages]
            return self._process_documents(documents, config.url)
        except Exception as e:
            logger.error(f"Recursive load error for {config.url}: {e}")
            return []

    async def load_single_page(self, config: CrawlConfig) -> List[Document]:
        try:
            response = requests.get(config.url, timeout=config.timeout)
            response.raise_for_status()
            text = self._clean_html(response.text)
            doc = Document(page_content=text, metadata={"source": config.url})
            return [doc]
        except Exception as e:
            logger.error(f"Single page load error for {config.url}: {e}")
            return []

    def _process_documents(self, documents: List[Document], source_url: str) -> List[Document]:
        for doc in documents:
            doc.page_content = self._clean_html(doc.page_content)
            doc.metadata["source"] = source_url
        return documents

    def _clean_html(self, html_content: str) -> str:
        soup = BeautifulSoup(html_content, "html.parser")
        for tag in soup(["script", "style", "noscript", "meta", "link", "head", "nav", "header", "footer"]):
            tag.decompose()
        return ' '.join(soup.get_text(separator=" ", strip=True).split())

