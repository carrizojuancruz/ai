import logging
from typing import Any, Dict, List
from urllib.parse import urlparse
from uuid import uuid4

from app.knowledge.crawler.service import CrawlerService
from app.knowledge.models import BulkSourceRequest, Source, SourceRequest
from app.knowledge.service import get_knowledge_service

from .repository import SourceRepository

logger = logging.getLogger(__name__)


class SourceService:

    def __init__(self):
        self.source_repo = SourceRepository()
        self.crawler_service = CrawlerService()
        self.knowledge_service = get_knowledge_service()

    async def get_all_sources(self) -> List[Source]:
        return self.source_repo.load_all()

    async def get_source_by_id(self, source_id: str) -> Source | None:
        return self.source_repo.find_by_id(source_id)

    async def create_source(self, request: SourceRequest) -> Dict[str, Any]:
        parsed = urlparse(request.url)
        if not (parsed.scheme and parsed.netloc):
            return {"success": False, "message": "Invalid URL"}

        existing = self.source_repo.find_by_url(request.url)
        if existing:
            self.knowledge_service.delete_source_documents(existing.id)
            self.source_repo.delete_by_id(existing.id)

        source = Source(id=str(uuid4()), name=request.name, url=request.url)

        self.source_repo.add(source)
        logger.info(f"Source created: {source.id}")

        try:
            crawl_result = await self.crawler_service.crawl_source(source.url)
            documents = crawl_result.get("documents", [])

            if documents:
                index_result = await self.knowledge_service.add_documents(documents, source.id)
                documents_indexed = index_result.get("documents_added", 0)
                return {
                    "source": source,
                    "documents_indexed": documents_indexed,
                    "success": True,
                    "message": f"Source created and {documents_indexed} documents indexed",
                }
            else:
                return {
                    "source": source,
                    "documents_indexed": 0,
                    "success": True,
                    "message": "Source created but no documents found",
                }
        except Exception as e:
            logger.error(f"Failed to process source {source.id}: {str(e)}")
            return {
                "source": source,
                "documents_indexed": 0,
                "success": False,
                "message": f"Source created but crawl failed: {str(e)}",
            }

    async def bulk_create_sources(self, request: BulkSourceRequest) -> Dict[str, Any]:
        results = []

        for source_request in request.sources:
            result = await self.create_source(source_request)
            results.append(result)

        total_sources = len(results)
        successful_crawls = sum(1 for r in results if r["success"])
        total_documents = sum(r["documents_indexed"] for r in results)

        return {
            "sources_created": total_sources,
            "successful_crawls": successful_crawls,
            "total_documents_indexed": total_documents,
            "results": results
        }

    async def delete_source(self, source_id: str) -> bool:
        """Delete source and associated documents."""
        if not self.source_repo.delete_by_id(source_id):
            return False

        if self.knowledge_service.delete_source_documents(source_id):
            logger.info(f"Source deleted: {source_id}")
        else:
            logger.warning(f"Source deleted but failed to delete vector documents for {source_id}")

        return True


_source_service: SourceService | None = None


def get_source_service() -> SourceService:
    global _source_service
    if _source_service is None:
        _source_service = SourceService()
    return _source_service
