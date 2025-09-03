import hashlib
import logging
import time
from typing import List

from langchain_aws import BedrockEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import config
from app.knowledge.models import Source

logger = logging.getLogger(__name__)


class DocumentService:

    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP,
            add_start_index=True
        )

        self.embeddings = BedrockEmbeddings(
            model_id=config.EMBEDDINGS_MODEL_ID,
            region_name=config.AWS_REGION
        )

    def split_documents(self, documents: List[Document], source: Source) -> List[Document]:
        """Split documents into chunks with source metadata."""
        all_chunks = []

        for doc in documents:
            doc.metadata["source_id"] = source.id

            doc.metadata["source_url"] = source.url

            if "source" in doc.metadata:
                doc.metadata["section_url"] = doc.metadata["source"]
            elif "url" not in doc.metadata:
                doc.metadata["section_url"] = source.url
            else:
                doc.metadata["section_url"] = doc.metadata.get("url", source.url)

            doc.metadata["name"] = source.name
            doc.metadata["type"] = source.type
            doc.metadata["category"] = source.category
            doc.metadata["description"] = source.description

            chunks = self.text_splitter.split_documents([doc])
            for chunk in chunks:
                chunk.metadata["content"] = doc.page_content
                chunk.metadata["content_hash"] = hashlib.sha256(chunk.page_content.encode()).hexdigest()
            all_chunks.extend(chunks)

        return all_chunks

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        start_time = time.time()
        embeddings = self.embeddings.embed_documents(texts)
        end_time = time.time()
        logger.info(f"Embedding generation completed in {end_time - start_time:.2f} seconds")
        return embeddings

    def generate_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for a single query."""
        return self.embeddings.embed_query(query)
