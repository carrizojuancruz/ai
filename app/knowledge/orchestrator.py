import hashlib
import logging
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
            created = updated = deleted = 0
            deletion_failures = []
            for local_source in local_sources:
                if local_source.url not in external_by_url:
                    deletion_result = await self._delete_source(local_source)
                    if deletion_result["success"]:
                        deleted += 1
                    else:
                        deletion_failures.append(deletion_result["error"])
            for ext_source in external_sources:
                if ext_source.url in local_by_url:
                    await self._update_source(local_by_url[ext_source.url], ext_source)
                    updated += 1
                else:
                    await self._create_source(ext_source)
                    created += 1

            kb_results = await self.sync_service.sync_sources()
            successful = sum(1 for r in kb_results if r.success)

            result = {
                "success": True,
                "sources_created": created,
                "sources_updated": updated,
                "sources_deleted": deleted,
                "sources_synced": successful,
                "sync_failures": len(kb_results) - successful
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
