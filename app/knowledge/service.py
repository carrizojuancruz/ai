import logging
from typing import Any, Dict, List
import time
from langchain_aws.embeddings import BedrockEmbeddings
from langchain_core.documents import Document

from app.knowledge import config
from .crawler.service import CrawlerService
from .document_service import DocumentService
from .repository import SourceRepository
from .vector_store.service import S3VectorStoreService

logger = logging.getLogger(__name__)


class KnowledgeService:
    
    def __init__(self):
        self.model = config.EMBEDDINGS_MODEL_ID
        self.region = config.AWS_REGION
        
        self.vector_store_service = S3VectorStoreService()
        self.crawler_service = CrawlerService()
        self.source_repo = SourceRepository()
        self.document_service = DocumentService()

        self.embeddings = BedrockEmbeddings(
            model_id=self.model,
            region_name=self.region
        )

    async def update_documents_for_source(self, documents: List[Document], source_id: str) -> Dict[str, Any]:
        if not documents:
            return {"documents_added": 0, "message": "No documents to add"}

        try:
            logger.info(f"Starting document processing for source {source_id}")
            self.vector_store_service.delete_documents(source_id)

            chunks = self.document_service.split_documents(documents, source_id)
            logger.info(f"Split {len(documents)} documents into {len(chunks)} chunks")

            if chunks:
                chunk_texts = self.document_service.prepare_texts_for_embedding(chunks)
                logger.info(f"Starting embedding generation for {len(chunk_texts)} chunks")
                start_time = time.time()
                chunk_embeddings = self.embeddings.embed_documents(chunk_texts)
                end_time = time.time()
                logger.info(f"Embedding generation completed in {end_time - start_time:.2f} seconds")

                self.vector_store_service.add_documents(chunks, chunk_embeddings)
                logger.info("Documents stored successfully")

            return {
                "documents_added": len(chunks),
                "original_documents": len(documents),
                "source_id": source_id,
                "storage_type": "s3_vectors",
                "message": f"Updated {len(documents)} documents into {len(chunks)} chunks for source {source_id}"
            }
        except Exception as e:
            logger.error(f"Failed processing source {source_id}: {str(e)}")
            raise Exception(f"Index update failed: {str(e)}")

    async def add_documents_to_index(self, documents: List[Document], source_id: str) -> Dict[str, Any]:
        return await self.update_documents_for_source(documents, source_id)

    async def search(self, query: str) -> List[Dict[str, Any]]:
        try:
            query_embedding = self.embeddings.embed_query(query)
            results = self.vector_store_service.similarity_search(query_embedding)
            out = []
            for r in results:
                meta = r.get('metadata', {})
                out.append({
                    'content': r.get('content', ''),
                    'source': meta.get('source', '')
                })
            return out
        except Exception:
            return []


_knowledge_service: KnowledgeService | None = None


def get_knowledge_service() -> KnowledgeService:
    global _knowledge_service
    if _knowledge_service is None:
        _knowledge_service = KnowledgeService()
    return _knowledge_service
