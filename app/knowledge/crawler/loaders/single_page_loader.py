import logging
from typing import List

from langchain_community.document_loaders import WebBaseLoader
from langchain_core.documents import Document

from .base_loader import BaseLoader

logger = logging.getLogger(__name__)


class SinglePageLoader(BaseLoader):

    async def load_documents(self) -> List[Document]:
        documents = []

        try:
            loader = WebBaseLoader(
                web_path=self.source.url,
                header_template=self.get_headers(),
                verify_ssl=False,
                continue_on_failure=True,
                raise_for_status=False,
                show_progress=False
            )

            raw_documents = loader.load()

            for doc in raw_documents:
                clean_content = self.clean_content(doc.page_content)
                standardized_doc = self.create_document(
                    content=clean_content,
                    url=doc.metadata.get("source", self.source.url),
                    loader_name="single_page"
                )
                documents.append(standardized_doc)

        except Exception as e:
            logger.error(f"Single page load error for {self.source.url}: {e}")

        return documents
