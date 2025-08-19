from typing import List
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


class DocumentService:    
    CHUNK_SIZE = 4000  
    CHUNK_OVERLAP = 400 
    
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.CHUNK_SIZE,
            chunk_overlap=self.CHUNK_OVERLAP,
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
