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

        sources_created = 0
        sources_updated = 0
        sources_deleted = 0
        sources_no_changes = 0
        sources_errors = 0
        sync_failures = []
        total_chunks_created = 0

        sources_to_delete = [source for url, source in kb_sources_by_url.items() if url not in external_sources_by_url]

        for source in sources_to_delete:
            deletion_result = self.kb_service.delete_source(source)
            if deletion_result["success"]:
                sources_deleted += 1
                logger.info(f"Deleted source: {source.url}")
            else:
                sources_errors += 1
                sync_failures.append({
                    "url": source.url,
                    "cause": f"Deletion failed: {deletion_result['error']['message']}"
                })
                logger.error(f"Failed to delete source {source.url}: {deletion_result['error']}")

        enabled_sources = [s for s in external_sources if s.enable]

        for external_source in enabled_sources:
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

                if not result["success"]:
                    sources_errors += 1
                    sync_failures.append({
                        "url": external_source.url,
                        "cause": result.get("message", "Unknown sync failure")
                    })
                    logger.error(f"Sync failed for {external_source.url}: {result.get('message', 'Unknown error')}")
                    continue

                chunks_added = result.get("documents_added", 0)

                if result["is_new_source"]:
                    sources_created += 1
                    total_chunks_created += chunks_added
                    logger.info(f"Created new source: {external_source.url} (+{chunks_added} chunks)")
                elif chunks_added > 0:
                    sources_updated += 1
                    total_chunks_created += chunks_added
                    logger.info(f"Updated source: {external_source.url} (+{chunks_added} chunks)")
                else:
                    sources_no_changes += 1
                    logger.info(f"No changes for source: {external_source.url}")

            except Exception as e:
                sources_errors += 1
                error_msg = str(e)
                if "ssl" in error_msg.lower() or "certificate" in error_msg.lower():
                    cause = f"SSL certificate error: {error_msg}"
                elif "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                    cause = f"Connection timeout: {error_msg}"
                elif "403" in error_msg or "forbidden" in error_msg.lower():
                    cause = f"Access forbidden: {error_msg}"
                elif "404" in error_msg or "not found" in error_msg.lower():
                    cause = f"Page not found: {error_msg}"
                else:
                    cause = f"Crawling error: {error_msg}"

                sync_failures.append({
                    "url": external_source.url,
                    "cause": cause
                })
                logger.error(f"Sync failed for {external_source.url}: {error_msg}")

        end_time = time.time()
        total_time = end_time - start_time

        result = {
            "success": True,
            "sources_created": sources_created,
            "sources_updated": sources_updated,
            "sources_deleted": sources_deleted,
            "sources_no_changes": sources_no_changes,
            "sources_errors": sources_errors,
            "total_chunks_created": total_chunks_created,
            "sync_failures": sync_failures,
            "total_sync_time_seconds": round(total_time, 2),
            "average_time_per_source": round(total_time / max(len(enabled_sources), 1), 2)
        }

        failure_count = len(sync_failures)

        logger.info(
            f"Knowledge base sync completed in {total_time:.2f}s: "
            f"Created: {sources_created}, Updated: {sources_updated}, "
            f"No changes: {sources_no_changes}, Deleted: {sources_deleted}, "
            f"Errors: {sources_errors}, Total chunks: {total_chunks_created}"
        )

        if sync_failures:
            logger.warning(f"Sync failures ({failure_count}):")
            for failure in sync_failures:
                logger.warning(f"  - {failure['url']}: {failure['cause']}")

        return result

