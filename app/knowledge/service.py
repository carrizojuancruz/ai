import logging
from typing import Any, Dict, List, Set

from app.core.config import config
from app.knowledge.models import Source
from app.knowledge.sources.repository import SourceRepository
from app.knowledge.vector_store.service import S3VectorStoreService

from .crawler.service import CrawlerService
from .document_service import DocumentService

logger = logging.getLogger(__name__)


class KnowledgeService:

    def __init__(self):
        self.vector_store_service = S3VectorStoreService()
        self.source_repository = SourceRepository()
        self.document_service = DocumentService()
        self.crawler_service = CrawlerService()

    def delete_source(self, source: Source) -> Dict[str, Any]:
        """Delete a source from the knowledge base."""
        deletion_result = self.vector_store_service.delete_documents_by_source_id(source.id)
        if deletion_result["success"]:
            self.source_repository.delete_by_url(source.url)
            logger.info(f"Successfully deleted source {source.url}")
            return {"success": True}
        else:
            error_info = {
                "url": source.url,
                "message": deletion_result["message"],
            }
            logger.error(f"Failed to delete vectors for source {source.id}: {deletion_result['message']}")
            return {"success": False, "error": error_info}

    async def upsert_source(self, source: Source) -> Dict[str, Any]:
        crawl_result = await self.crawler_service.crawl_source(source)
        documents = crawl_result.get("documents", [])
        if not documents:
            return {
                "source_url": source.url,
                "success": False,
                "message": "No documents found during crawl"
            }

        chunks = self.document_service.split_documents(documents, source)
        new_hashes = {doc.metadata.get("content_hash") for doc in chunks}

        existing_source = self.source_repository.find_by_url(source.url)
        is_update = existing_source is not None

        if is_update:
            if not self._needs_reindex(existing_source.id, new_hashes):
                logger.info(f"No changes detected for {source.url} - skipping reindex")
                return {
                    "source_url": source.url,
                    "success": True,
                    "message": "No changes detected",
                    "is_new_source": False
                }

            logger.info(f"Source {source.url} needs reindexing - deleting old documents")
            delete_result = self.delete_source(existing_source)
            if not delete_result["success"]:
                logger.error(f"Failed to delete existing source during reindex: {delete_result['error']}")
                return {
                    "source_url": source.url,
                    "success": False,
                    "message": f"Failed to delete existing documents: {delete_result['error']['message']}"
                }

        chunk_texts = [doc.page_content for doc in chunks]
        chunk_embeddings = self.document_service.generate_embeddings(chunk_texts)

        self.vector_store_service.add_documents(chunks, chunk_embeddings)

        self.source_repository.upsert(source)

        return {
                "success": True,
                "documents_added": len(chunks),
                "source_url": source.url,
                "is_new_source": not is_update
            }

    async def search(self, query: str) -> List[Dict[str, Any]]:
        try:
            query_embedding = self.document_service.generate_query_embedding(query)
            results = self.vector_store_service.similarity_search(query_embedding, k=config.TOP_K_SEARCH)
            out = []
            for r in results:
                meta = r.get('metadata', {})
                out.append({
                    'content': r.get('content', ''),
                    'section_url': meta.get('section_url', ''),
                    'source_url': meta.get('source_url', ''),
                    'source_id': meta.get('source_id', ''),
                    'name': meta.get('name', ''),
                    'type': meta.get('type', ''),
                    'category': meta.get('category', ''),
                    'description': meta.get('description', '')
                })
            return out
        except Exception:
            return []

    def get_sources(self) -> List[Source]:
        """Get all knowledge base sources."""
        return self.source_repository.load_all()

    def _needs_reindex(self, source_id: str, new_hashes: Set[str]) -> bool:
        """Check if source needs complete reindexing by comparing hash sets."""
        old_hashes = self.vector_store_service.get_source_chunk_hashes(source_id)
        needs_reindex = old_hashes != new_hashes

        if needs_reindex:
            logger.info(f"Changes detected for source_id {source_id}: {len(old_hashes)} → {len(new_hashes)} chunks")

        return needs_reindex


_knowledge_service: KnowledgeService | None = None


def get_knowledge_service() -> KnowledgeService:
    global _knowledge_service
    if _knowledge_service is None:
        _knowledge_service = KnowledgeService()
    return _knowledge_service
