import logging
from typing import List

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

from .base_loader import BaseLoader

logger = logging.getLogger(__name__)


class PDFLoader(BaseLoader):

    async def load_documents(self) -> List[Document]:
        try:
            loader = PyPDFLoader(self.source.url)
            raw_documents = loader.load()

            return [
                self.create_document(
                    content=self.clean_content(doc.page_content),
                    url=self.source.url,
                    loader_name="pdf",
                    page_number=doc.metadata.get("page", 0)
                )
                for doc in raw_documents
            ]
        except Exception as e:
            logger.error(f"PDF load error for {self.source.url}: {e}")
            return []
