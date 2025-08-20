import os
import logging
from typing import Any, Dict, List
from langchain_core.documents import Document
from langchain_aws.embeddings import BedrockEmbeddings
from dotenv import load_dotenv

from .models import KBSearchResult
from .document_service import DocumentService
from .vector_store.service import VectorStoreService
from .crawler.service import CrawlerService
from .repository import SourceRepository

load_dotenv()

logger = logging.getLogger(__name__)


class KnowledgeService:
    DEFAULT_SEARCH_K = 3
    MODEL = os.getenv("EMBEDDINGS_MODEL_ID", "amazon.titan-embed-text-v2:0")
    REGION = os.getenv("AWS_REGION", "us-east-1")

    def __init__(self, 
                 vector_store_service: VectorStoreService = None,
                 crawler_service: CrawlerService = None,
                 source_repo: SourceRepository = None,
                 document_service: DocumentService = None):
        self.vector_store = vector_store_service or VectorStoreService()
        self.crawler = crawler_service or CrawlerService()
        self.source_repo = source_repo or SourceRepository()
        self.document_service = document_service or DocumentService()
        
        self.embeddings = BedrockEmbeddings(
            model_id=self.MODEL,
            region_name=self.REGION
        )

    async def update_documents_for_source(self, documents: List[Document], source_id: str) -> Dict[str, Any]:
        if not documents:
            return {"documents_added": 0, "message": "No documents to add"}
            
        try:
            logger.info(f"Starting document processing for source {source_id}")
            self.vector_store.delete_documents(source_id)
            
            chunks = self.document_service.split_documents(documents, source_id)
            logger.info(f"Split {len(documents)} documents into {len(chunks)} chunks")
            
            if chunks:
                chunk_texts = self.document_service.prepare_texts_for_embedding(chunks)
                logger.info(f"Starting embedding generation for {len(chunk_texts)} chunks")
                import time
                start_time = time.time()
                chunk_embeddings = self.embeddings.embed_documents(chunk_texts)
                end_time = time.time()
                logger.info(f"Embedding generation completed in {end_time - start_time:.2f} seconds")
                
                self.vector_store.add_documents(chunks, chunk_embeddings)
                logger.info(f"Documents stored successfully")
            
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

    async def search(self, query: str, k: int = None) -> List[Dict[str, Any]]:
        k = k or self.DEFAULT_SEARCH_K
        try:
            query_embedding = self.embeddings.embed_query(query)
            results = self.vector_store.search(query_embedding, k=k)
            out = []
            for r in results:
                meta = r.get('metadata', {})
                out.append({
                    'content': r.get('content', ''),
                    'source': meta.get('source', '')
                })
            return out
        except Exception as e:
            return []


_knowledge_service: KnowledgeService | None = None


def get_knowledge_service() -> KnowledgeService:
    global _knowledge_service
    if _knowledge_service is None:
        _knowledge_service = KnowledgeService()
    return _knowledge_service
