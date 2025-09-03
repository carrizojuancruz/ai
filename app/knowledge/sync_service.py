import hashlib
import logging
from typing import Any, Dict

from app.core.config import config
from app.knowledge.models import Source
from app.services.external_context.sources.repository import ExternalSourcesRepository

from .service import KnowledgeService

logger = logging.getLogger(__name__)


class KnowledgeBaseSyncService:
    def __init__(self):
        self.external_repo = ExternalSourcesRepository()
        self.kb_service = KnowledgeService()

    async def sync_all(self) -> Dict[str, Any]:
        external_sources = await self.external_repo.get_all()
        kb_sources = self.kb_service.get_sources()

        external_sources_by_url = {s.url: s for s in external_sources}
        kb_sources_by_url = {s.url: s for s in kb_sources}

        created_count = 0
        updated_count = 0
        deleted_count = 0
        deletion_failures = []
        synced_urls = []
        failed_urls = []

        sources_to_delete = [source for url, source in kb_sources_by_url.items() if url not in external_sources_by_url]

        for source in sources_to_delete:
            logger.info(f"Deleting source {source.url}")
            deletion_result = self.kb_service.delete_source(source)
            if deletion_result["success"]:
                deleted_count += 1
                logger.info(f"Successfully deleted source: {source.url}")
            else:
                deletion_failures.append(deletion_result["error"])
                logger.error(f"Failed to delete source {source.url}: {deletion_result['error']}")

        for external_source in external_sources:
            logger.info(f"Processing source {external_source.url}")

            if not external_source.enable:
                continue

            try:
                source_id = hashlib.sha256(external_source.url.encode()).hexdigest()[:16]

                internal_source = Source(
                    id=source_id,
                    name=external_source.name,
                    url=external_source.url,
                    type=external_source.type,
                    category=external_source.category,
                    description=external_source.description,
                    include_path_patterns=external_source.include_path_patterns,
                    exclude_path_patterns=external_source.exclude_path_patterns,
                    total_max_pages=str(external_source.total_max_pages) if external_source.total_max_pages else str(config.CRAWL_MAX_PAGES),
                    recursion_depth=str(external_source.recursion_depth) if external_source.recursion_depth else str(config.CRAWL_MAX_DEPTH)
                )

                result = await self.kb_service.upsert_source(internal_source)

                if result["is_new_source"]:
                    created_count += 1
                else:
                    updated_count += 1

                synced_urls.append(external_source.url)
                logger.info(f"Successfully synced: {external_source.url}")
            except Exception as e:
                failed_urls.append(external_source.url)
                logger.error(f"Sync failed for {external_source.url}: {str(e)}")

        result = {
            "success": True,
            "sources_created": created_count,
            "sources_updated": updated_count,
            "sources_deleted": deleted_count,
            "sources_synced": synced_urls,
            "sync_failures": failed_urls
        }
        if deletion_failures:
            result["deletion_failures"] = deletion_failures

        return result

