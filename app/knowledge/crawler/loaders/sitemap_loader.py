import logging
from typing import List

from langchain_community.document_loaders import SitemapLoader as LangchainSitemapLoader
from langchain_core.documents import Document

from app.knowledge.crawler.content_utils import UrlFilter

from .base_loader import BaseLoader

logger = logging.getLogger(__name__)


class SitemapLoader(BaseLoader):

    async def load_documents(self) -> List[Document]:
        try:
            max_pages = self.kwargs.get('max_pages', self.source.total_max_pages)

            def sitemap_filter(url: str) -> bool:
                return not UrlFilter.should_exclude_url(url)

            loader = LangchainSitemapLoader(
                web_path=self.source.url,
                filter_urls=sitemap_filter
            )

            raw_documents = loader.load()[:max_pages]

            return [
                self.create_document(
                    content=doc.page_content,
                    url=doc.metadata.get("source", self.source.url),
                    loader_name="sitemap"
                )
                for doc in raw_documents
            ]
        except Exception as e:
            logger.error(f"Sitemap load error for {self.source.url}: {e}")
            return []
