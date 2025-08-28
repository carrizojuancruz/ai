import logging
from typing import List, Set

from app.knowledge.crawler.service import CrawlerService
from app.knowledge.models import Source, SyncResult
from app.knowledge.service import KnowledgeService
from app.knowledge.sources.repository import SourceRepository
from app.knowledge.vector_store.service import S3VectorStoreService

logger = logging.getLogger(__name__)

class SyncService:

    def __init__(self):
        self.vector_store = S3VectorStoreService()
        self.crawler = CrawlerService()
        self.knowledge_service = KnowledgeService()
        self.source_repo = SourceRepository()


    def needs_reindex(self, source_id: str, new_hashes: Set[str]) -> bool:
        """Check if source needs complete reindexing by comparing hash sets."""
        old_hashes = self.vector_store.get_source_chunk_hashes(source_id)
        return old_hashes != new_hashes

    async def sync_source(self, source: Source) -> SyncResult:
        """Sync a single source using parent-child strategy."""
        try:
            crawl_result = await self.crawler.crawl_source(source.url)
            documents = crawl_result.get("documents", [])

            if not documents:
                return SyncResult(
                    source_id=source.id,
                    success=False,
                    message="No documents found during crawl"
                )

            chunks = self.knowledge_service._split_documents(documents, source)
            new_hashes = {doc.metadata.get("content_hash") for doc in chunks}

            if self.needs_reindex(source.id, new_hashes):
                self.vector_store.delete_documents(source.id)

                await self.knowledge_service.add_documents(documents, source)

                return SyncResult(
                    source_id=source.id,
                    success=True,
                    message="Source reindexed due to content changes",
                    chunks_reindexed=len(chunks),
                    has_changes=True
                )
            else:
                return SyncResult(
                    source_id=source.id,
                    success=True,
                    message="No changes detected",
                    chunks_reindexed=0,
                    has_changes=False
                )

        except Exception as e:
            logger.error(f"Failed to sync source {source.id}: {str(e)}")
            return SyncResult(
                source_id=source.id,
                success=False,
                message=f"Sync failed: {str(e)}"
            )

    async def sync_sources(self) -> List[SyncResult]:
        """Sync all sources using parent-child strategy."""
        try:
            sources = self.source_repo.load_all()
            logger.info(f"Starting sync for {len(sources)} sources")

            results = []
            for source in sources:
                if source.enabled:
                    logger.info(f"Syncing source: {source.id} - {source.url}")
                    result = await self.sync_source(source)
                    results.append(result)
                else:
                    logger.info(f"Skipping disabled source: {source.id}")

            successful_syncs = sum(1 for r in results if r.success)
            changed_sources = sum(1 for r in results if r.has_changes)

            logger.info(f"Sync completed: {successful_syncs}/{len(results)} successful, {changed_sources} sources had changes")
            return results

        except Exception as e:
            logger.error(f"Failed to sync sources: {str(e)}")
            return []
