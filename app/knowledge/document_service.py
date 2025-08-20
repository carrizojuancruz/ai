from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.knowledge import config


class DocumentService:

    def __init__(self):
        self.chunk_size = config.CHUNK_SIZE
        self.chunk_overlap = config.CHUNK_OVERLAP
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            add_start_index=True
        )

    def split_documents(self, documents: List[Document], source_id: str) -> List[Document]:
        all_chunks = []

        for doc in documents:
            doc.metadata["source_id"] = source_id
            chunks = self.text_splitter.split_documents([doc])
            all_chunks.extend(chunks)

        return all_chunks

    def prepare_texts_for_embedding(self, documents: List[Document]) -> List[str]:
        return [doc.page_content for doc in documents]
