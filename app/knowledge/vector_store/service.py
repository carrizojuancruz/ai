import hashlib
from typing import Any, Dict, List

import boto3
from langchain_core.documents import Document
from app.knowledge import config


class S3VectorStoreService:
    def __init__(self):
        self.bucket_name = config.S3_VECTOR_NAME
        self.index_name = config.VECTOR_INDEX_NAME
        self.client = boto3.client('s3vectors', region_name=config.AWS_REGION)

    def add_documents(self, documents: List[Document], embeddings: List[List[float]]):
        vectors = []
        for i, (doc, embedding) in enumerate(zip(documents, embeddings, strict=False)):
            source_url = doc.metadata.get('source', '')
            source_id = doc.metadata.get('source_id', '')
            content_hash = doc.metadata.get('content_hash', '')  
            unique_key = f"doc_{content_hash}" if content_hash else f"doc_{source_id}_{i}"

            metadata: Dict[str, Any] = {
                'source': source_url,
                'source_id': source_id,
                'chunk_index': i,
                'chunk_content': doc.page_content,
                'content_hash': content_hash 
            }

            vectors.append({
                'key': unique_key,
                'data': {'float32': [float(x) for x in embedding]},
                'metadata': metadata
            })

        self.client.put_vectors(
            vectorBucketName=self.bucket_name,
            indexName=self.index_name,
            vectors=vectors
        )

    def delete_documents(self, source_id: str):
        try:
            self.client.delete_vectors(
                vectorBucketName=self.bucket_name,
                indexName=self.index_name,
                filter={'source_id': source_id}
            )
        except Exception:
            pass

    def get_source_chunk_hashes(self, source_id: str) -> set[str]:
        """Get all content hashes for a specific source using pagination to avoid topK limits."""
        try:
            hashes = set()
            paginator = self.client.get_paginator('list_vectors')
            
            # Use paginator to get all vectors with metadata only
            page_iterator = paginator.paginate(
                vectorBucketName=self.bucket_name,
                indexName=self.index_name,
                returnMetadata=True,
                returnData=False,  # We only need metadata, not vector data
                PaginationConfig={
                    'PageSize': 1000  # Process in batches of 1000
                }
            )
            
            for page in page_iterator:
                for vector in page.get('vectors', []):
                    metadata = vector.get('metadata', {})
                    # Filter by source_id and collect hashes
                    if metadata.get('source_id') == source_id:
                        content_hash = metadata.get('content_hash')
                        if content_hash:
                            hashes.add(content_hash)
            
            return hashes
        except Exception:
            return set()

    def similarity_search(self, query_embedding: List[float], k: int) -> List[Dict[str, Any]]:
        response = self.client.query_vectors(
            vectorBucketName=self.bucket_name,
            indexName=self.index_name,
            topK=k,
            queryVector={'float32': [float(x) for x in query_embedding]},
            returnMetadata=True,
            returnDistance=True
        )

        return [{
            'content': v['metadata'].get('chunk_content', ''),
            'metadata': {
                'source': v['metadata'].get('source', ''),
                'source_id': v['metadata'].get('source_id', ''),
                'chunk_index': v['metadata'].get('chunk_index', 0),
                'content_hash': v['metadata'].get('content_hash', ''),
                **v['metadata']
            },
            'score': 1 - v.get('distance', 0),
            'vector_key': v.get('key', '')
        } for v in response.get('vectors', [])]
