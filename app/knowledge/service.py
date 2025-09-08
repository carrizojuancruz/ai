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
        import time
        start_time = time.time()

        crawl_result = await self.crawler_service.crawl_source(source)
        documents = crawl_result.get("documents", [])

        if not documents:
            logger.info(f"No documents found during crawl for {source.url}")
            return {
                "source_url": source.url,
                "success": True,
                "message": "No documents found during crawl",
                "is_new_source": False,
                "documents_added": 0
            }

        logger.info(f"Processing {len(documents)} documents from {source.url}")

        chunks = self.document_service.split_documents(documents, source)
        logger.info(f"Split into {len(chunks)} chunks for {source.url}")

        original_chunk_count = len(chunks)
        if len(chunks) > config.MAX_CHUNKS_PER_SOURCE:
            chunks = chunks[:config.MAX_CHUNKS_PER_SOURCE]
            logger.info(f"Limited chunks from {original_chunk_count} to {config.MAX_CHUNKS_PER_SOURCE} for {source.url}")

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
                    "is_new_source": False,
                    "documents_added": 0
                }

            logger.info(f"Source {source.url} needs reindexing - deleting old documents")
            delete_result = self.delete_source(existing_source)
            if not delete_result["success"]:
                logger.error(f"Failed to delete existing source during reindex: {delete_result['error']}")
                return {
                    "source_url": source.url,
                    "success": False,
                    "message": f"Failed to delete existing documents: {delete_result['error']['message']}",
                    "is_new_source": False,
                    "documents_added": 0
                }

        logger.info(f"Generating embeddings for {len(chunks)} chunks from {source.url}")
        chunk_texts = [doc.page_content for doc in chunks]
        chunk_embeddings = self.document_service.generate_embeddings(chunk_texts)

        section_urls = set()
        for chunk in chunks:
            section_url = chunk.metadata.get("section_url")
            if section_url:
                section_urls.add(section_url)

        source.section_urls = list(section_urls) if section_urls else []
        logger.info(f"Collected {len(source.section_urls)} unique section URLs for {source.url}")

        self.vector_store_service.add_documents(chunks, chunk_embeddings)

        source.total_chunks = len(chunks)
        self.source_repository.upsert(source)

        end_time = time.time()
        processing_time = end_time - start_time

        result = {
            "success": True,
            "documents_added": len(chunks),
            "source_url": source.url,
            "is_new_source": not is_update,
            "processing_time_seconds": round(processing_time, 2)
        }

        logger.debug(f"Successfully upserted {source.url}: {len(chunks)} chunks in {processing_time:.2f}s")

        return result

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

    def get_source_details(self, source_id: str) -> Dict[str, Any]:
        """Get detailed information about a source including chunk count and content.

        Args:
            source_id: The source ID to get details for

        """
        sources = self.get_sources()
        source = next((s for s in sources if s.id == source_id), None)
        if not source:
            return {"error": f"Source with id {source_id} not found"}

        chunks = []
        total_chunks = 0

        try:
            for vector in self.vector_store_service._iterate_vectors_by_source_id(source_id):
                total_chunks += 1
                metadata = vector.get('metadata', {})

                chunks.append({
                    'section_url': metadata.get('section_url', ''),
                    'content': metadata.get('content', '')
                })

        except Exception as e:
            logger.error(f"Error retrieving chunk metadata: {str(e)}")

        result = {
            "source": {
                "id": source.id,
                "name": source.name,
                "url": source.url,
                "type": source.type,
                "category": source.category,
                "description": source.description,
                "total_max_pages": source.total_max_pages,
                "recursion_depth": source.recursion_depth,
                "last_sync": source.last_sync,
                "section_urls": source.section_urls or []
            },
            "total_chunks": total_chunks,
            "chunks": chunks
        }

        logger.info(f"Returning {len(chunks)} chunks for source {source_id}")
        return result


_knowledge_service: KnowledgeService | None = None


def get_knowledge_service() -> KnowledgeService:
    global _knowledge_service
    if _knowledge_service is None:
        _knowledge_service = KnowledgeService()
    return _knowledge_service
