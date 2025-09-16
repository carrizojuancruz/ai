import hashlib
import logging
import time
from typing import Any, Dict

from app.knowledge.models import Source
from app.services.external_context.sources.repository import ExternalSourcesRepository

from .crawl_logger import CrawlLogger
from .service import KnowledgeService

logger = logging.getLogger(__name__)


class KnowledgeBaseSyncService:
    def __init__(self):
        self.external_repo = ExternalSourcesRepository()
        self.kb_service = KnowledgeService()
        self.crawl_logger = CrawlLogger()
        self.default_max_pages = 20
        self.default_recursion_depth = 2

    async def sync_all(self, limit: int = None) -> Dict[str, Any]:
        start_time = time.time()

        external_sources_available = True
        try:
            external_sources = await self.external_repo.get_all()
            logger.info(f"Retrieved {len(external_sources)} external sources")
        except Exception as e:
            logger.error(f"Failed to retrieve external sources: {e}")
            external_sources = []
            external_sources_available = False

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

        enabled_sources = [s for s in external_sources if s.enable]

        if limit is not None:
            if limit == 0:
                enabled_sources = []
                logger.info("Skipping source sync (limit=0)")
            elif limit > 0:
                enabled_sources = enabled_sources[:limit]
                logger.info(f"Limited to {len(enabled_sources)} source{'s' if len(enabled_sources) != 1 else ''}")
            else:
                logger.warning(f"Invalid limit {limit}, processing all sources")

        if enabled_sources:
            logger.info(f"Processing {len(enabled_sources)} source{'s' if len(enabled_sources) != 1 else ''}")
            self.crawl_logger.log_sync_start(len(external_sources), len(enabled_sources))

        for external_source in enabled_sources:
            logger.info(f"Processing: {external_source.url}")

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
                        "cause": "Sync failed"
                    })
                    logger.error(f"Sync failed: {external_source.url}")
                    self.crawl_logger.log_error(external_source.url, "Sync failed", "Internal processing error")
                    continue

                chunks_added = result.get("documents_added", 0)
                documents_processed = result.get("documents_processed", 0)
                result_message = result.get("message", "")
                crawl_error = result.get("crawl_error")

                if result["is_new_source"]:
                    sources_created += 1
                    total_chunks_created += chunks_added
                    logger.info(f"Created: {external_source.url} (+{chunks_added} chunks)")
                    self.crawl_logger.log_success(external_source.url, documents_processed, chunks_added, True)
                elif chunks_added > 0:
                    sources_updated += 1
                    total_chunks_created += chunks_added
                    logger.info(f"Updated: {external_source.url} (+{chunks_added} chunks)")
                    self.crawl_logger.log_success(external_source.url, documents_processed, chunks_added, False)
                elif crawl_error or "No documents found during crawl" in result_message:
                    # This is actually a crawling error, not "no changes"
                    sources_errors += 1
                    error_detail = crawl_error if crawl_error else "No documents found during crawl"
                    sync_failures.append({
                        "url": external_source.url,
                        "cause": "Crawling failed"
                    })
                    logger.error(f"Crawl failed for {external_source.url}: {error_detail}")
                    self.crawl_logger.log_error(external_source.url, error_detail, "Crawling failed")
                else:
                    # This is actual "no changes" (content hash matched)
                    sources_no_changes += 1
                    logger.info(f"No changes: {external_source.url}")
                    self.crawl_logger.log_success(external_source.url, documents_processed, 0, False)

            except Exception as e:
                sources_errors += 1
                error_msg = str(e)
                if "ssl" in error_msg.lower() or "certificate" in error_msg.lower():
                    cause = "SSL certificate error"
                elif "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                    cause = "Connection timeout"
                elif "403" in error_msg or "forbidden" in error_msg.lower():
                    cause = "Access forbidden"
                elif "404" in error_msg or "not found" in error_msg.lower():
                    cause = "Page not found"
                else:
                    cause = "Crawling error"

                sync_failures.append({
                    "url": external_source.url,
                    "cause": cause
                })
                logger.error(f"Sync failed for {external_source.url}: {error_msg}")
                self.crawl_logger.log_error(external_source.url, error_msg, cause)

        if external_sources_available:
            if limit is not None:
                enabled_sources_by_url = {s.url: s for s in enabled_sources}
                sources_to_delete = [source for url, source in kb_sources_by_url.items() if url not in enabled_sources_by_url]
            else:
                sources_to_delete = [source for url, source in kb_sources_by_url.items() if url not in external_sources_by_url]

            if sources_to_delete:
                logger.info(f"Deleting {len(sources_to_delete)} obsolete sources")

            for source in sources_to_delete:
                deletion_result = self.kb_service.delete_source(source)
                if deletion_result["success"]:
                    sources_deleted += 1
                    logger.info(f"Deleted source: {source.url}")
                    self.crawl_logger.log_deletion(source.url, True)
                else:
                    sources_errors += 1
                    sync_failures.append({
                        "url": source.url,
                        "cause": "Deletion failed"
                    })
                    logger.error(f"Failed to delete source {source.url}")
                    self.crawl_logger.log_deletion(source.url, False)
        else:
            logger.warning("Skipping deletions - external sources unavailable")

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
            "average_time_per_source": round(total_time / max(len(enabled_sources), 1), 2),
            "external_sources_available": external_sources_available,
            "deletions_skipped": not external_sources_available
        }

        deletion_info = " (deletions skipped)" if not external_sources_available else ""

        logger.info(
            f"Sync completed in {total_time:.2f}s: "
            f"Created {sources_created}, Updated {sources_updated}, "
            f"Unchanged {sources_no_changes}, Deleted {sources_deleted}, "
            f"Errors {sources_errors}, Chunks {total_chunks_created}{deletion_info}"
        )

        # Log sync completion to crawl log
        self.crawl_logger.log_sync_complete(
            sources_created, sources_updated, sources_no_changes,
            sources_deleted, sources_errors, total_time
        )

        if sync_failures:
            logger.warning(f"{len(sync_failures)} failures occurred:")
            for failure in sync_failures:
                logger.warning(f"  {failure['url']}: {failure['cause']}")

        return result

