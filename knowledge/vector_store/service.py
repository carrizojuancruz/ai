import hashlib
import os
from typing import Any, Dict, List

import boto3
from dotenv import load_dotenv
from langchain_core.documents import Document

load_dotenv()


class S3VectorStoreService:
    def __init__(self):
        self.bucket_name = os.getenv("S3_VECTOR_NAME")
        self.index_name = os.getenv("VECTOR_INDEX_NAME")
        self.top_k_search = int(os.getenv("TOP_K_SEARCH"))
        self.client = boto3.client('s3vectors', region_name=os.getenv("AWS_REGION"))

    def add_documents(self, documents: List[Document], embeddings: List[List[float]]):
        vectors = []
        for i, (doc, embedding) in enumerate(zip(documents, embeddings, strict=False)):
            source_url = doc.metadata.get('source', '')
            source_id = doc.metadata.get('source_id', '')
            content_hash = hashlib.md5(f"{source_url}_{source_id}_{i}".encode()).hexdigest()[:12]
            unique_key = f"doc_{content_hash}"

            metadata: Dict[str, Any] = {
                'source': source_url,
                'source_id': source_id,
                'chunk_index': i,
            }

            if isinstance(doc.page_content, str):
                metadata['content'] = doc.page_content
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

    def similarity_search(self, query_embedding: List[float], k: int = None) -> List[Dict[str, Any]]:
        k = k or self.top_k_search
        response = self.client.query_vectors(
            vectorBucketName=self.bucket_name,
            indexName=self.index_name,
            topK=k,
            queryVector={'float32': [float(x) for x in query_embedding]},
            returnMetadata=True,
            returnDistance=True
        )

        return [{
            'content': v['metadata'].get('content', ''),
            'metadata': {
                'source': v['metadata'].get('source', ''),
                'source_id': v['metadata'].get('source_id', ''),
                'chunk_index': v['metadata'].get('chunk_index', 0),
                **v['metadata']
            },
            'score': 1 - v.get('distance', 0),
            'vector_key': v.get('key', '')
        } for v in response.get('vectors', [])]
