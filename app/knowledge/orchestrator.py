import hashlib
import logging
from datetime import datetime
from typing import Any, Dict

from app.knowledge.models import Source
from app.knowledge.sources.repository import SourceRepository
from app.knowledge.sync.service import SyncService
from app.services.external_context.sources.repository import ExternalSourcesRepository

logger = logging.getLogger(__name__)


class KnowledgeBaseOrchestrator:
    def __init__(self):
        self.external_repo = ExternalSourcesRepository()
        self.local_repo = SourceRepository()
        self.sync_service = SyncService()

    def _generate_source_id(self, url: str) -> str:
        """Generate source ID from URL using SHA256 hash."""
        return hashlib.sha256(url.encode()).hexdigest()

    async def sync_all(self) -> Dict[str, Any]:
        try:
            external_sources = await self.external_repo.get_all()
            local_sources = self.local_repo.load_all()
            external_by_url = {s.url: s for s in external_sources}
            local_by_url = {s.url: s for s in local_sources}

            created_count = 0
            updated_count = 0
            deleted_count = 0
            deletion_failures = []

            sources_to_delete = [s for s in local_sources if s.url not in external_by_url]
            for i, local_source in enumerate(sources_to_delete, 1):
                logger.info(f"Deleting source {i}/{len(sources_to_delete)}: {local_source.url}")
                deletion_result = await self._delete_source(local_source)
                if deletion_result["success"]:
                    deleted_count += 1
                    logger.info(f"Successfully deleted source: {local_source.url}")
                else:
                    deletion_failures.append(deletion_result["error"])
                    logger.error(f"Failed to delete source {local_source.url}: {deletion_result['error']}")

            for i, ext_source in enumerate(external_sources, 1):
                logger.info(f"Processing source {i}/{len(external_sources)}: {ext_source.url}")

                if ext_source.url in local_by_url:
                    await self._update_source(local_by_url[ext_source.url], ext_source)
                    updated_count += 1
                    logger.info(f"Updated source: {ext_source.url}")
                else:
                    await self._create_source(ext_source)
                    created_count += 1
                    logger.info(f"Created source: {ext_source.url}")

            logger.info("Starting document synchronization for all sources")
            kb_results = await self.sync_service.sync_sources()
            synced_urls = []
            failed_urls = []

            for i, result in enumerate(kb_results, 1):
                source = self.local_repo.find_by_id(result.source_id)
                if source:
                    logger.info(f"Sync result {i}/{len(kb_results)}: {source.url} - {'SUCCESS' if result.success else 'FAILED'}")
                    if result.success:
                        synced_urls.append(source.url)
                    else:
                        failed_urls.append(source.url)
                        logger.error(f"Document sync failed for {source.url}: {result.message}")

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
        except Exception as e:
            logger.error(f"Sync operation failed: {str(e)}")
            return {"success": False, "message": str(e)}

    async def _delete_source(self, source: Source) -> Dict[str, Any]:
        """Delete a source from both vector store and local repository."""
        try:
            deletion_result = self.sync_service.vector_store.delete_documents_by_source_id(source.id)
            if deletion_result["success"]:
                self.local_repo.delete_by_id(source.id)
                logger.info(f"Successfully deleted source {source.id}")
                return {"success": True}
            else:
                error_info = {
                    "url": source.url,
                    "source_id": source.id,
                    "message": deletion_result["message"]
                }
                logger.error(f"Failed to delete vectors for source {source.id}: {deletion_result['message']}")
                return {"success": False, "error": error_info}
        except Exception as e:
            error_info = {
                "url": source.url,
                "source_id": source.id,
                "message": str(e)
            }
            logger.error(f"Exception during source deletion {source.id}: {str(e)}")
            return {"success": False, "error": error_info}

    async def _create_source(self, ext_source) -> None:
        """Create a new source in local repository."""
        source = Source(
            id=self._generate_source_id(ext_source.url),
            name=ext_source.name,
            url=ext_source.url,
            enabled=ext_source.enable,
            type=ext_source.type or "",
            category=ext_source.category or "",
            description=ext_source.description or "",
            include_path_patterns=ext_source.include_path_patterns or "",
            exclude_path_patterns=ext_source.exclude_path_patterns or "",
            total_max_pages=str(ext_source.total_max_pages) if ext_source.total_max_pages else "",
            recursion_depth=str(ext_source.recursion_depth) if ext_source.recursion_depth else ""
        )
        self.local_repo.add(source)

    async def _update_source(self, existing_source: Source, ext_source) -> None:
        """Update an existing source with external data."""
        updated_source = Source(
            id=existing_source.id,
            name=ext_source.name,
            url=ext_source.url,
            enabled=ext_source.enable,
            type=ext_source.type or "",
            category=ext_source.category or "",
            description=ext_source.description or "",
            include_path_patterns=ext_source.include_path_patterns or "",
            exclude_path_patterns=ext_source.exclude_path_patterns or "",
            total_max_pages=str(ext_source.total_max_pages) if ext_source.total_max_pages else "",
            recursion_depth=str(ext_source.recursion_depth) if ext_source.recursion_depth else ""
        )
        self.local_repo.update(updated_source)

    async def run_background_sync(self, job_id: str) -> None:
        """Execute the knowledge base sync with detailed progress logging."""
        start_time = datetime.utcnow()

        try:
            logger.info(f"Starting knowledge sync job {job_id}")

            external_sources = await self.external_repo.get_all()
            logger.info(f"Job {job_id}: Starting sync with {len(external_sources)} sources")

            result = await self.sync_all()
            duration = (datetime.utcnow() - start_time).total_seconds()

            sync_failures = result.get('sync_failures', [])
            deletion_failures = result.get('deletion_failures', [])
            sync_failure_info = [f"{url}: sync failed" for url in sync_failures] if sync_failures else []
            deletion_failure_info = [f"{fail['url']}: {fail['message']}" for fail in deletion_failures] if deletion_failures else []
            all_failures = sync_failure_info + deletion_failure_info

            logger.info(
                f"Job {job_id} completed successfully in {duration:.2f}s: "
                f"Created: {result.get('sources_created', 0)}, "
                f"Updated: {result.get('sources_updated', 0)}, "
                f"Deleted: {result.get('sources_deleted', 0)}, "
                f"Synced: {result.get('sources_synced', [])}, "
                f"Failures: {all_failures}"
            )

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"Job {job_id} failed after {duration:.2f}s: {str(e)}")
            raise
