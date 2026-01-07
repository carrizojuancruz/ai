import logging
from datetime import datetime
from typing import Any, Dict, List

from app.knowledge.models import Source
from app.knowledge.vector_store.service import S3VectorStoreService

from .crawler.service import CrawlerService
from .document_service import DocumentService

logger = logging.getLogger(__name__)


class KnowledgeService:

    TOP_K_SEARCH = 10
    
    def __init__(self):
        self.vector_store_service = S3VectorStoreService()
        self.document_service = DocumentService()
        self.crawler_service = CrawlerService()

    def delete_all_vectors(self) -> Dict[str, Any]:
        """Delete ALL vectors from the knowledge base."""
        deletion_result = self.vector_store_service.delete_all_vectors()

        if deletion_result["success"]:
            logger.info("Successfully deleted all vectors from knowledge base")
            return {
                "success": True,
                "vectors_deleted": deletion_result["vectors_deleted"],
                "message": deletion_result["message"]
            }
        else:
            logger.error(f"Failed to delete all vectors: {deletion_result['message']}")
            return {
                "success": False,
                "error": deletion_result["message"],
                "vectors_deleted": deletion_result["vectors_deleted"],
                "vectors_failed": deletion_result["vectors_failed"]
            }

    def delete_source_vectors_by_id(self, source_id: str) -> Dict[str, Any]:
        """Delete all vectors for a source by source_id."""
        deletion_result = self.vector_store_service.delete_documents_by_source_id(source_id)

        if deletion_result["success"]:
            logger.info(f"Successfully deleted {deletion_result['vectors_deleted']} vectors for source {source_id}")
            return {
                "success": True,
                "vectors_found": deletion_result.get("vectors_found", 0),
                "vectors_deleted": deletion_result["vectors_deleted"],
                "message": deletion_result["message"]
            }
        else:
            logger.error(f"Failed to delete vectors for source {source_id}: {deletion_result.get('message')}")
            return {
                "success": False,
                "error": deletion_result.get("message", "Unknown error"),
                "vectors_found": deletion_result.get("vectors_found", 0),
                "vectors_deleted": deletion_result.get("vectors_deleted", 0),
                "vectors_failed": deletion_result.get("vectors_failed", 0)
            }

    def delete_source(self, source_url: str) -> Dict[str, Any]:
        """Delete a source from the knowledge base."""
        vector_sources = self.get_vector_sources()
        source_data = next(
            (s for s in vector_sources['sources'] if s['url'] == source_url),
            None
        )
        if not source_data:
            return {"success": False, "error": f"Source not found: {source_url}"}

        source_id = source_data['source_id']
        deletion_result = self.vector_store_service.delete_documents_by_source_id(source_id)
        if deletion_result["success"]:
            logger.info(f"Successfully deleted source {source_url}")
            return {"success": True}
        else:
            error_info = {
                "url": source_url,
                "message": deletion_result["message"],
            }
            logger.error(f"Failed to delete vectors for source {source_id}: {deletion_result['message']}")
            return {"success": False, "error": error_info}

    async def upsert_source(self, source: Source, content_source: str = "external") -> Dict[str, Any]:
        import time
        start_time = time.time()

        crawl_result = await self.crawler_service.crawl_source(source)
        documents = crawl_result.get("documents", [])
        crawl_error = crawl_result.get("error")

        if not documents:
            logger.info(f"No documents found during crawl for {source.url}")
            error_message = crawl_result.get("message", "No documents found during crawl")
            return {
                "source_url": source.url,
                "success": True,
                "message": error_message,
                "crawl_error": crawl_error,
                "is_new_source": False,
                "documents_added": 0,
                "documents_processed": 0
            }

        logger.info(f"Processing {len(documents)} documents from {source.url}")

        chunks = self.document_service.split_documents(documents, source, content_source)
        logger.info(f"Split into {len(chunks)} chunks for {source.url}")

        vector_sources = self.get_vector_sources()
        existing_source_data = next(
            (s for s in vector_sources['sources'] if s['source_id'] == source.id),
            None
        )
        is_update = existing_source_data is not None

        if is_update:
            logger.info(f"Source exists with source_id={source.id}, url={source.url} - deleting all old documents for clean replacement")
            delete_result = self.delete_source_vectors_by_id(source.id)
            if not delete_result["success"]:
                logger.error(f"Failed to delete existing source during replacement: {delete_result.get('error')}")
                return {
                    "source_url": source.url,
                    "success": False,
                    "message": f"Failed to delete existing documents: {delete_result.get('error', 'Unknown error')}",
                    "is_new_source": False,
                    "documents_added": 0,
                    "documents_processed": len(documents)
                }
            logger.info(f"✅ Deleted {delete_result['vectors_deleted']} old chunks (found {delete_result['vectors_found']}) for source_id={source.id}, url={source.url}")

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

        end_time = time.time()
        processing_time = end_time - start_time

        result = {
            "success": True,
            "documents_added": len(chunks),
            "documents_processed": len(documents),
            "source_url": source.url,
            "is_new_source": not is_update,
            "processing_time_seconds": round(processing_time, 2)
        }

        logger.debug(f"Successfully upserted {source.url}: {len(chunks)} chunks in {processing_time:.2f}s")

        return result

    async def search(self, query: str, filter: Dict[str, str] | None = None) -> List[Dict[str, Any]]:
        """Search the knowledge base with optional metadata filtering."""
        try:
            query_embedding = self.document_service.generate_query_embedding(query)
            results = self.vector_store_service.similarity_search(
                query_embedding,
                k=self.TOP_K_SEARCH,
                metadata_filter=filter
            )
            out = []
            for r in results:
                meta = r.get('metadata', {})
                result = {
                    'content': r.get('content', ''),
                    'section_url': meta.get('section_url', ''),
                    'source_url': meta.get('source_url', ''),
                    'source_id': meta.get('source_id', ''),
                    'name': meta.get('name', ''),
                    'type': meta.get('type', ''),
                    'category': meta.get('category', ''),
                    'description': meta.get('description', ''),
                    'content_source': meta.get('content_source', ''),
                    'score': r.get('score', 0.0),
                }

                if 'subcategory' in meta:
                    result['subcategory'] = meta['subcategory']

                out.append(result)
            return out
        except Exception as e:
            logger.error(f"Search failed: {str(e)}", exc_info=True)
            return []

    def get_sources(self) -> List[Source]:
        """Get all knowledge base sources from vector store."""
        vector_sources_data = self.get_vector_sources()

        sources = []
        for s in vector_sources_data['sources']:
            try:
                last_sync = None
                if s.get('last_sync'):
                    try:
                        last_sync = datetime.fromisoformat(s['last_sync'])
                    except (ValueError, TypeError):
                        logger.warning(f"Failed to parse last_sync for source {s['source_id']}: {s.get('last_sync')}")

                source = Source(
                    id=s['source_id'],
                    name=s['name'],
                    url=s['url'],
                    type=s.get('type', ''),
                    category=s.get('category', ''),
                    description=s.get('description', ''),
                    total_chunks=s.get('total_chunks', 0),
                    section_urls=s.get('section_urls', []),
                    last_sync=last_sync,
                    content_source=s.get('content_source', 'external')
                )
                sources.append(source)
            except Exception as e:
                logger.warning(f"Failed to create Source from vector data: {e}")
                continue

        return sources

    def get_source_details(self, source_id: str) -> Dict[str, Any]:
        """Get detailed information about a source including chunk count and content.

        Args:
            source_id: The source ID to get details for

        """
        vector_sources = self.get_vector_sources()
        source_data = next(
            (s for s in vector_sources['sources'] if s['source_id'] == source_id),
            None
        )
        if not source_data:
            return {"error": f"Source with id {source_id} not found"}

        chunks = []
        total_chunks = 0
        section_urls = set()
        last_sync = None

        try:
            for vector in self.vector_store_service._iterate_vectors_by_source_id(source_id):
                total_chunks += 1
                metadata = vector.get('metadata', {})
                section_url = metadata.get('url', '')

                if section_url:
                    section_urls.add(section_url)

                chunk_last_sync = metadata.get('last_sync')
                if chunk_last_sync and (not last_sync or chunk_last_sync > last_sync):
                    last_sync = chunk_last_sync

                chunks.append(metadata)

        except Exception as e:
            logger.error(f"Error retrieving chunk metadata: {str(e)}")

        parsed_last_sync = None
        if last_sync:
            try:
                parsed_last_sync = datetime.fromisoformat(last_sync)
            except (ValueError, TypeError):
                logger.warning(f"Failed to parse last_sync timestamp: {last_sync}")

        result = {
            "source": {
                "id": source_data['source_id'],
                "name": source_data['name'],
                "url": source_data['url'],
                "type": source_data.get('type', ''),
                "category": source_data.get('category', ''),
                "description": source_data.get('description', ''),
                "total_max_pages": None,
                "recursion_depth": None,
                "last_sync": parsed_last_sync.isoformat() if parsed_last_sync else None,
                "section_urls": sorted(list(section_urls))
            },
            "total_chunks": total_chunks,
            "chunks": chunks
        }

        logger.info(f"Returning {len(chunks)} chunks for source {source_id}")
        return result

    def get_vector_sources(self) -> dict[str, Any]:
        """Get all unique sources from the vector store."""
        try:

            vectors_metadata = self.vector_store_service.get_all_vectors_metadata()

            sources_dict: dict[str, dict[str, Any]] = {}

            for metadata in vectors_metadata:
                source_id = metadata.get('source_id')
                if not source_id:
                    continue

                if source_id not in sources_dict:
                    sources_dict[source_id] = {
                        'source_id': source_id,
                        'name': metadata.get('name', ''),
                        'url': metadata.get('url', ''),
                        'type': metadata.get('type', ''),
                        'category': metadata.get('category', ''),
                        'description': metadata.get('description', ''),
                        'content_source': metadata.get('content_source', ''),
                        'last_sync': metadata.get('last_sync'),
                        'total_chunks': 0,
                        'section_urls': set()
                    }
                else:
                    chunk_last_sync = metadata.get('last_sync')
                    if chunk_last_sync:
                        current_last_sync = sources_dict[source_id]['last_sync']
                        if not current_last_sync or chunk_last_sync > current_last_sync:
                            sources_dict[source_id]['last_sync'] = chunk_last_sync

                sources_dict[source_id]['total_chunks'] += 1

                section_url = metadata.get('url', '')
                if section_url:
                    sources_dict[source_id]['section_urls'].add(section_url)

            for source_data in sources_dict.values():
                source_data['section_urls'] = sorted(list(source_data['section_urls']))

            sources = sorted(
                sources_dict.values(),
                key=lambda x: x.get('total_chunks', 0),
                reverse=True
            )

            logger.info(f"Successfully aggregated {len(sources)} unique sources from {len(vectors_metadata)} vectors")

            return {
                'sources': sources,
                'total_sources': len(sources)
            }

        except Exception as e:
            logger.error(f"Error in get_vector_sources: {str(e)}")
            raise


_knowledge_service: KnowledgeService | None = None


def get_knowledge_service() -> KnowledgeService:
    global _knowledge_service
    if _knowledge_service is None:
        _knowledge_service = KnowledgeService()
    return _knowledge_service
