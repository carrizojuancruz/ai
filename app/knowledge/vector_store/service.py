import logging
from typing import Any, Dict, List

import boto3
from langchain_core.documents import Document

from app.core.config import config

logger = logging.getLogger(__name__)


class S3VectorStoreService:
    def __init__(self):
        self.bucket_name = config.S3V_BUCKET
        self.index_name = config.S3V_INDEX_KB
        self.client = boto3.client('s3vectors', region_name=config.AWS_REGION)

    def add_documents(self, documents: List[Document], embeddings: List[List[float]]):
        vectors = []
        for i, (doc, embedding) in enumerate(zip(documents, embeddings, strict=False)):
            content_hash = doc.metadata.get('content_hash', '')
            source_id = doc.metadata.get('source_id', '')

            content_hash = doc.metadata['content_hash']
            key = f"doc_{content_hash}"

            vectors.append({
                'key': key,
                'data': {'float32': [float(x) for x in embedding]},
                'metadata': {
                    'source': doc.metadata.get('source', ''),
                    'source_id': source_id,
                    'chunk_index': i,
                    'chunk_content': doc.page_content,
                    'content_hash': content_hash,
                    'source_type': doc.metadata.get('source_type', ''),
                    'source_category': doc.metadata.get('source_category', ''),
                    'source_description': doc.metadata.get('source_description', '')
                }
            })

        self.client.put_vectors(
            vectorBucketName=self.bucket_name,
            indexName=self.index_name,
            vectors=vectors
        )

    def delete_documents_by_source_id(self, source_id: str) -> dict[str, any]:
        """Delete all documents for a given source_id. Returns detailed results."""
        try:
            vector_keys = self._get_vector_keys_by_source_id(source_id)

            if not vector_keys:
                return {
                    "success": True,
                    "vectors_found": 0,
                    "vectors_deleted": 0,
                    "message": "No vectors found to delete"
                }

            batch_size = 100
            deleted_count = 0
            failed_keys = []

            for i in range(0, len(vector_keys), batch_size):
                batch_keys = vector_keys[i:i + batch_size]
                try:
                    self.client.delete_vectors(
                        vectorBucketName=self.bucket_name,
                        indexName=self.index_name,
                        keys=batch_keys
                    )
                    deleted_count += len(batch_keys)
                except Exception as batch_error:
                    logger.error(f"Failed to delete batch {i//batch_size + 1}: {str(batch_error)}")
                    failed_keys.extend(batch_keys)

            total_found = len(vector_keys)
            success = deleted_count > 0 and len(failed_keys) == 0

            result = {
                "success": success,
                "vectors_found": total_found,
                "vectors_deleted": deleted_count,
                "vectors_failed": len(failed_keys)
            }

            if success:
                result["message"] = f"Successfully deleted all {deleted_count} vectors"
            elif deleted_count > 0:
                result["message"] = f"Partially successful: deleted {deleted_count}/{total_found} vectors"
                result["failed_keys"] = failed_keys
            else:
                result["message"] = "Failed to delete any vectors"
                result["failed_keys"] = failed_keys
            return result
        except Exception as e:
            logger.error(f"Failed to delete documents for source_id {source_id}: {str(e)}")
            return {
                "success": False,
                "vectors_found": 0,
                "vectors_deleted": 0,
                "vectors_failed": 0,
                "message": f"Deletion process failed: {str(e)}"
            }

    def _iterate_vectors_by_source_id(self, source_id: str):
        """Yield vectors for a specific source_id."""
        try:
            paginator = self.client.get_paginator('list_vectors')
            page_iterator = paginator.paginate(
                vectorBucketName=self.bucket_name,
                indexName=self.index_name,
                returnMetadata=True,
                returnData=False,
                PaginationConfig={'PageSize': 1000}
            )

            for page in page_iterator:
                for vector in page.get('vectors', []):
                    if vector.get('metadata', {}).get('source_id') == source_id:
                        yield vector
        except Exception as e:
            logger.error(f"Failed to iterate vectors for source_id {source_id}: {str(e)}")

    def _get_vector_keys_by_source_id(self, source_id: str) -> list[str]:
        """Get all vector keys for a specific source_id."""
        return [v.get('key') for v in self._iterate_vectors_by_source_id(source_id) if v.get('key')]


    def get_source_chunk_hashes(self, source_id: str) -> set[str]:
        """Get all content hashes for a specific source."""
        hashes = set()
        for vector in self._iterate_vectors_by_source_id(source_id):
            content_hash = vector.get('metadata', {}).get('content_hash')
            if content_hash:
                hashes.add(content_hash)
        return hashes

    def similarity_search(self, query_embedding: List[float], k: int) -> List[Dict[str, Any]]:
        response = self.client.query_vectors(
            vectorBucketName=self.bucket_name,
            indexName=self.index_name,
            topK=k,
            queryVector={'float32': [float(x) for x in query_embedding]},
            returnMetadata=True,
            returnDistance=True
        )

        results = []
        for v in response.get('vectors', []):
            metadata = v.get('metadata', {})
            results.append({
                'content': metadata.get('chunk_content', ''),
                'metadata': {
                    'source': metadata.get('source', ''),
                    'source_id': metadata.get('source_id', ''),
                    'chunk_index': metadata.get('chunk_index', 0),
                    'content_hash': metadata.get('content_hash', ''),
                    'source_type': metadata.get('source_type', ''),
                    'source_category': metadata.get('source_category', ''),
                    'source_description': metadata.get('source_description', ''),
                    **metadata
                },
                'score': 1 - v.get('distance', 0),
                'vector_key': v.get('key', '')
            })
        return results
