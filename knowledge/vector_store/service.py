import os
import boto3
from typing import List, Dict, Any
import hashlib
from langchain_core.documents import Document
from dotenv import load_dotenv

load_dotenv()


class S3VectorStore:    
    DEFAULT_INDEX_NAME = "web-sources"
    DEFAULT_AWS_REGION = "us-east-1"
    
    def __init__(self):
        self.bucket_name = os.getenv("S3_VECTOR_NAME")
        self.index_name = os.getenv("VECTOR_INDEX_NAME", self.DEFAULT_INDEX_NAME)
        self.client = boto3.client('s3vectors', region_name=os.getenv("AWS_REGION", self.DEFAULT_AWS_REGION))
    
    def add_documents(self, documents: List[Document], embeddings: List[List[float]]):
        vectors = []
        for i, (doc, embedding) in enumerate(zip(documents, embeddings)):
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
    
    def similarity_search(self, query_embedding: List[float], k: int = 4) -> List[Dict[str, Any]]:
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


class VectorStoreService:
    
    def __init__(self, vector_store: S3VectorStore = None):
        self.vector_store = vector_store or S3VectorStore()
    
    def add_documents(self, documents: List[Document], embeddings: List[List[float]]):
        return self.vector_store.add_documents(documents, embeddings)
    
    def delete_documents(self, source_id: str):
        return self.vector_store.delete_documents(source_id)
    
    def search(self, query_embedding: List[float], k: int = 4) -> List[Dict[str, Any]]:
        return self.vector_store.similarity_search(query_embedding, k)
