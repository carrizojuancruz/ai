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
        """Add documents to vector store."""
        vectors = []
        for i, (doc, embedding) in enumerate(zip(documents, embeddings, strict=False)):
            content_hash = doc.metadata.get('content_hash', '')
            source_id = doc.metadata.get('source_id', '')

            key = f"doc_{source_id[:16]}_{content_hash[:16]}_{i}"

            metadata = {
                'source_id': source_id,
                'content_hash': content_hash,
                'chunk_index': i,
                'content': doc.page_content,
                'content_source': doc.metadata.get('content_source', 'unknown'),
                'name': doc.metadata.get('name') or doc.metadata.get('filename', ''),
                'url': doc.metadata.get('section_url') or doc.metadata.get('source_url', ''),
                'type': doc.metadata.get('type') or doc.metadata.get('file_type', ''),
                'category': doc.metadata.get('category', ''),
                'description': doc.metadata.get('description', ''),
                'last_sync': doc.metadata.get('last_sync'),
            }

            vectors.append({
                'key': key,
                'data': {'float32': [float(x) for x in embedding]},
                'metadata': metadata
            })

        try:
            self.client.put_vectors(
                vectorBucketName=self.bucket_name,
                indexName=self.index_name,
                vectors=vectors
            )
        except Exception as e:
            logger.error(f"Failed to store vectors: {str(e)}")
            raise

    def delete_all_vectors(self) -> dict[str, any]:
        """Delete ALL vectors from the index."""
        try:
            vector_keys = self._get_all_vector_keys()

            if not vector_keys:
                logger.info("No vectors found in index")
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
                    logger.info(f"Deleted batch {i//batch_size + 1}: {len(batch_keys)} vectors")
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
                result["message"] = f"Successfully deleted all {deleted_count} vectors from index"
                logger.info(f"Successfully deleted all {deleted_count} vectors from index")
            elif deleted_count > 0:
                result["message"] = f"Partially successful: deleted {deleted_count}/{total_found} vectors"
                result["failed_keys"] = failed_keys
                logger.warning(f"Partially deleted vectors from index: {deleted_count}/{total_found}")
            else:
                result["message"] = "Failed to delete any vectors"
                result["failed_keys"] = failed_keys
                logger.error("Failed to delete any vectors from index")

            return result
        except Exception as e:
            logger.error(f"Failed to delete all vectors from index: {str(e)}")
            return {
                "success": False,
                "vectors_found": 0,
                "vectors_deleted": 0,
                "vectors_failed": 0,
                "message": f"Deletion process failed: {str(e)}"
            }

    def _get_all_vector_keys(self) -> list[str]:
        """Get all vector keys from the index."""
        vector_keys = []
        try:
            paginator = self.client.get_paginator('list_vectors')
            page_iterator = paginator.paginate(
                vectorBucketName=self.bucket_name,
                indexName=self.index_name,
                returnMetadata=False,
                returnData=False,
                PaginationConfig={'PageSize': 1000}
            )

            for page in page_iterator:
                for vector in page.get('vectors', []):
                    key = vector.get('key')
                    if key:
                        vector_keys.append(key)

            logger.info(f"Found {len(vector_keys)} total vectors in index")
            return vector_keys
        except Exception as e:
            logger.error(f"Failed to get all vector keys: {str(e)}")
            return []

    def delete_documents_by_source_id(self, source_id: str) -> dict[str, any]:
        """Delete all documents for a given source_id."""
        try:
            vector_keys = self._get_vector_keys_by_source_id(source_id)

            if not vector_keys:
                logger.info(f"No vectors found for source {source_id}")
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
                logger.info(f"Successfully deleted all {deleted_count} vectors for source {source_id}")
            elif deleted_count > 0:
                result["message"] = f"Partially successful: deleted {deleted_count}/{total_found} vectors"
                result["failed_keys"] = failed_keys
                logger.warning(f"Partially deleted vectors for source {source_id}: {deleted_count}/{total_found}")
            else:
                result["message"] = "Failed to delete any vectors"
                result["failed_keys"] = failed_keys
                logger.error(f"Failed to delete any vectors for source {source_id}")

            return result
        except Exception as e:
            logger.error(f"Failed to delete documents for source {source_id}: {str(e)}")
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
        """Get all content hashes for a specific source_id."""
        hashes = set()
        for vector in self._iterate_vectors_by_source_id(source_id):
            content_hash = vector.get('metadata', {}).get('content_hash')
            if content_hash:
                hashes.add(content_hash)

        return hashes

    def similarity_search(
        self,
        query_embedding: List[float],
        k: int,
        metadata_filter: Dict[str, str] | None = None
    ) -> List[Dict[str, Any]]:
        """Perform similarity search with optional metadata filtering.

        Args:
            query_embedding: Query vector embedding
            k: Number of top results to return
            metadata_filter: Optional metadata filter dict, e.g. {"content_source": "internal"}

        Returns:
            List of search results with content, metadata, score, and vector_key

        """
        query_params = {
            'vectorBucketName': self.bucket_name,
            'indexName': self.index_name,
            'topK': k,
            'queryVector': {'float32': [float(x) for x in query_embedding]},
            'returnMetadata': True,
            'returnDistance': True
        }

        if metadata_filter:
            if metadata_filter == {"content_source": "external"}:
                logger.info("Skipping filter for content_source='external' to include documents without the field")
                metadata_filter = None

            if metadata_filter:
                if len(metadata_filter) == 1:
                    field, value = next(iter(metadata_filter.items()))
                    query_params['filter'] = {field: value}
                else:
                    conditions = [
                        {field: value}
                        for field, value in metadata_filter.items()
                    ]
                    query_params['filter'] = {"$and": conditions}
                logger.info(f"Performing filtered search with: {metadata_filter}")

        response = self.client.query_vectors(**query_params)

        results = []
        for v in response.get('vectors', []):
            metadata = v.get('metadata', {})
            url = metadata.get('url', '')

            results.append({
                'content': metadata.get('content', ''),
                'metadata': {
                    'source_id': metadata.get('source_id', ''),
                    'content_hash': metadata.get('content_hash', ''),
                    'chunk_index': metadata.get('chunk_index', 0),
                    'content_source': metadata.get('content_source', ''),
                    'name': metadata.get('name', ''),
                    'url': url,
                    'type': metadata.get('type', ''),
                    'category': metadata.get('category', ''),
                    'description': metadata.get('description', ''),
                    'section_url': url,
                    'source_url': url,
                },
                'score': 1 - v.get('distance', 0),
                'vector_key': v.get('key', '')
            })
        return results

    def get_all_vectors_metadata(self) -> list[dict[str, Any]]:
        """Get metadata from all vectors in the store.

        Returns:
            List of vector metadata dictionaries

        """
        try:
            logger.info("Fetching all vector metadata from vector store")
            vectors_metadata = []

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
                    metadata = vector.get('metadata', {})
                    if metadata:
                        vectors_metadata.append(metadata)

            logger.info(f"Retrieved metadata from {len(vectors_metadata)} vectors")
            return vectors_metadata

        except Exception as e:
            logger.error(f"Failed to get vectors metadata: {str(e)}")
            raise

