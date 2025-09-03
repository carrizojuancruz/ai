import hashlib
import logging
from typing import Any, Dict

from app.knowledge.models import Source
from app.services.external_context.sources.repository import ExternalSourcesRepository

from .service import KnowledgeService

logger = logging.getLogger(__name__)


class KnowledgeBaseSyncService:
    def __init__(self):
        self.external_repo = ExternalSourcesRepository()
        self.kb_service = KnowledgeService()
        self.default_max_pages = 20
        self.default_recursion_depth = 2

    async def sync_all(self) -> Dict[str, Any]:
        import time
        start_time = time.time()

        external_sources = await self.external_repo.get_all()
        kb_sources = self.kb_service.get_sources()

        external_sources_by_url = {s.url: s for s in external_sources}
        kb_sources_by_url = {s.url: s for s in kb_sources}

        created_count = 0
        updated_count = 0
        deleted_count = 0
        total_documents_processed = 0
        total_chunks_created = 0
        deletion_failures = []
        synced_urls = []
        failed_urls = []


        sources_to_delete = [source for url, source in kb_sources_by_url.items() if url not in external_sources_by_url]

        for source in sources_to_delete:
            deletion_result = self.kb_service.delete_source(source)
            if deletion_result["success"]:
                deleted_count += 1
            else:
                deletion_failures.append(deletion_result["error"])
                logger.error(f"Failed to delete source {source.url}: {deletion_result['error']}")

        enabled_sources = [s for s in external_sources if s.enable]

        for external_source in external_sources:
            if not external_source.enable:
                logger.debug(f"Skipping disabled source: {external_source.url}")
                continue

            source_start_time = time.time()
            logger.info(f"Processing source {external_source.url}")

            try:
                source_id = hashlib.sha256(external_source.url.encode()).hexdigest()[:16]

                max_pages = external_source.total_max_pages or self.default_max_pages
                max_depth = external_source.recursion_depth or self.default_recursion_depth

                internal_source = Source(
                    id=source_id,
                    name=external_source.name,
                    url=external_source.url,
                    type=external_source.type,
                    category=external_source.category,
                    description=external_source.description,
                    include_path_patterns=external_source.include_path_patterns,
                    exclude_path_patterns=external_source.exclude_path_patterns,
                    total_max_pages=max_pages,
                    recursion_depth=max_depth
                )

                result = await self.kb_service.upsert_source(internal_source)

                if result["is_new_source"]:
                    created_count += 1
                    chunks_added = result.get("documents_added", 0)
                    total_chunks_created += chunks_added
                    logger.info(f"Created new source: {external_source.url} (+{chunks_added} chunks)")
                elif result.get("documents_added", 0) > 0:
                    updated_count += 1
                    chunks_added = result.get("documents_added", 0)
                    total_chunks_created += chunks_added
                    logger.info(f"Updated source: {external_source.url} (+{chunks_added} chunks)")
                else:
                    logger.info(f"No changes for source: {external_source.url}")

                total_documents_processed += 1
                synced_urls.append(external_source.url)

                source_end_time = time.time()
                processing_time = source_end_time - source_start_time
                logger.debug(f"Sync completed for {external_source.url} in {processing_time:.2f}s")

            except Exception as e:
                failed_urls.append(external_source.url)
                logger.error(f"Sync failed for {external_source.url}: {str(e)}")

        end_time = time.time()
        total_time = end_time - start_time

        result = {
            "success": True,
            "sources_created": created_count,
            "sources_updated": updated_count,
            "sources_deleted": deleted_count,
            "sources_processed": total_documents_processed,
            "total_chunks_created": total_chunks_created,
            "sources_synced": synced_urls,
            "sync_failures": failed_urls,
            "total_sync_time_seconds": round(total_time, 2),
            "average_time_per_source": round(total_time / max(len(enabled_sources), 1), 2)
        }

        if deletion_failures:
            result["deletion_failures"] = deletion_failures

        logger.info(f"Knowledge base sync completed in {total_time:.2f}s: {created_count} created, {updated_count} updated, {deleted_count} deleted, {len(failed_urls)} failed")

        return result

