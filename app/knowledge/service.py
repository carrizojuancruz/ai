import hashlib
import logging
import time
from typing import Any, Dict, List

from langchain_aws import BedrockEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.knowledge import config
from app.knowledge.models import Source
from app.knowledge.vector_store.service import S3VectorStoreService

logger = logging.getLogger(__name__)


class KnowledgeService:

    def __init__(self):
        self.vector_store_service = S3VectorStoreService()

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP,
            add_start_index=True
        )

        self.embeddings = BedrockEmbeddings(
            model_id=config.EMBEDDINGS_MODEL_ID,
            region_name=config.AWS_REGION
        )

    async def add_documents(self, documents: List[Document], source: Source) -> Dict[str, Any]:
        if not documents:
            return {"documents_added": 0, "message": "No documents to add"}

        try:
            logger.info(f"Starting document processing for source {source.id}")
            self.vector_store_service.delete_documents(source.id)

            chunks = self._split_documents(documents, source)
            logger.info(f"Split {len(documents)} documents into {len(chunks)} chunks")

            if chunks:
                chunk_texts = [doc.page_content for doc in chunks]
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
                "source_id": source.id,
                "storage_type": "s3_vectors",
                "message": f"Updated {len(documents)} documents into {len(chunks)} chunks for source {source.id}"
            }
        except Exception as e:
            logger.error(f"Failed processing source {source.id}: {str(e)}")
            raise Exception(f"Index update failed: {str(e)}") from e

    async def search(self, query: str) -> List[Dict[str, Any]]:
        try:
            query_embedding = self.embeddings.embed_query(query)
            results = self.vector_store_service.similarity_search(query_embedding, k=config.TOP_K_SEARCH)
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

    def delete_source_documents(self, source_id: str) -> bool:
        """Delete all documents for a given source."""
        try:
            self.vector_store_service.delete_documents(source_id)
            logger.info(f"Deleted documents for source: {source_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete documents for source {source_id}: {str(e)}")
            return False

    def _split_documents(self, documents: List[Document], source: Source) -> List[Document]:
        all_chunks = []

        for doc in documents:
            doc.metadata["source_id"] = source.id
            doc.metadata["source_type"] = source.type or ""
            doc.metadata["source_category"] = source.category or ""
            doc.metadata["source_description"] = source.description or ""
            chunks = self.text_splitter.split_documents([doc])
            for chunk in chunks:
                chunk.metadata["content_hash"] = hashlib.sha256(chunk.page_content.encode()).hexdigest()
            all_chunks.extend(chunks)

        return all_chunks


_knowledge_service: KnowledgeService | None = None


def get_knowledge_service() -> KnowledgeService:
    global _knowledge_service
    if _knowledge_service is None:
        _knowledge_service = KnowledgeService()
    return _knowledge_service
