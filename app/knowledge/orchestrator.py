from typing import Any, Dict

from app.knowledge.models import Source
from app.knowledge.sources.repository import SourceRepository
from app.knowledge.sync.service import SyncService
from app.services.external_context.sources.repository import ExternalSourcesRepository


class KnowledgeBaseOrchestrator:
    def __init__(self):
        self.external_repo = ExternalSourcesRepository()
        self.local_repo = SourceRepository()
        self.sync_service = SyncService()

    async def sync_all(self) -> Dict[str, Any]:
        try:
            # Get external sources and sync to local
            external_sources = await self.external_repo.get_all()
            local_urls = {s.url for s in self.local_repo.load_all()}

            # Delete sources not in external
            deleted = 0
            for source in self.local_repo.load_all():
                if source.url not in {s.url for s in external_sources}:
                    self.sync_service.vector_store.delete_documents(source.id)
                    self.local_repo.delete_by_id(source.id)
                    deleted += 1

            # Update local sources
            created = updated = 0
            for ext in external_sources:
                source = Source(id=ext.id, name=ext.name, url=ext.url, enabled=ext.enabled,
                              type=ext.type or "", category=ext.category or "", description=ext.description or "")
                if ext.url in local_urls:
                    source.id = self.local_repo.find_by_url(ext.url).id
                    self.local_repo.update(source)
                    updated += 1
                else:
                    self.local_repo.add(source)
                    created += 1

            # Sync to knowledge base
            kb_results = await self.sync_service.sync_sources()
            successful = sum(1 for r in kb_results if r.success)

            return {
                "success": True,
                "sources_created": created,
                "sources_updated": updated,
                "sources_deleted": deleted,
                "kb_synced": successful,
                "kb_failed": len(kb_results) - successful
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_status(self) -> Dict[str, Any]:
        sources = self.local_repo.load_all()
        return {
            "total_sources": len(sources),
            "enabled_sources": sum(1 for s in sources if s.enabled)
        }
