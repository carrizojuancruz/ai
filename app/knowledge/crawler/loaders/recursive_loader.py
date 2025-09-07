import logging
from typing import List

from langchain_community.document_loaders import RecursiveUrlLoader
from langchain_core.documents import Document

from app.core.config import config
from app.knowledge.crawler.content_utils import UrlFilter

from .base_loader import BaseLoader

logger = logging.getLogger(__name__)


class RecursiveLoader(BaseLoader):

    async def load_documents(self) -> List[Document]:
        documents = []

        try:
            exclude_dirs = UrlFilter.build_exclude_dirs(self.source)
            max_docs_to_crawl = min(
                self.kwargs.get('max_pages', self.source.total_max_pages),
                config.MAX_DOCUMENTS_PER_SOURCE
            )
            max_depth = self.kwargs.get('max_depth', self.source.recursion_depth)

            loader = RecursiveUrlLoader(
                url=self.source.url,
                max_depth=max_depth,
                prevent_outside=True,
                timeout=config.CRAWL_TIMEOUT,
                exclude_dirs=exclude_dirs,
                extractor=self.clean_content,
                check_response_status=False,
                continue_on_failure=True,
                headers=self.get_headers(),
                ssl=False
            )

            raw_documents = loader.load()[:max_docs_to_crawl]

            for doc in raw_documents:
                standardized_doc = self.create_document(
                    content=doc.page_content,
                    url=doc.metadata.get("source", self.source.url),
                    loader_name="recursive"
                )
                documents.append(standardized_doc)

        except Exception as e:
            logger.error(f"Recursive load error for {self.source.url}: {e}")

        return documents
