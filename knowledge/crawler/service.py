from typing import Any, Dict

from ..repository import SourceRepository
from .loaders import CrawlConfig, WebLoader


class CrawlerService:

    def __init__(self, source_repo: SourceRepository = None, web_loader: WebLoader = None):
        self.source_repo = source_repo or SourceRepository()
        self.web_loader = web_loader or WebLoader()

    async def crawl_source(self, source_id: str) -> Dict[str, Any]:
        source = self.source_repo.find_by_id(source_id)
        if not source:
            raise ValueError("Source not found")

        config = self._create_config(source)
        documents = await self._load_documents(config)

        return {
            "documents": documents,
            "documents_loaded": len(documents),
            "source_id": source_id,
            "message": f"Successfully loaded {len(documents)} documents"
        }

    def _create_config(self, source) -> CrawlConfig:
        return CrawlConfig(url=source.url)

    async def _load_documents(self, config: CrawlConfig):
        if config.crawl_type == "single":
            return await self.web_loader.load_single_page(config)
        elif config.crawl_type == "sitemap":
            return await self.web_loader.load_sitemap(config)
        else:
            return await self.web_loader.load_recursive(config)
