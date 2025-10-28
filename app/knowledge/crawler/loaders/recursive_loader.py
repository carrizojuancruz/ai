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
        try:
            exclude_dirs = UrlFilter.build_exclude_dirs(self.source)

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

            raw_documents = loader.load()

            max_pages = self.kwargs.get('max_pages', self.source.total_max_pages)
            if max_pages and len(raw_documents) > max_pages:
                raw_documents = raw_documents[:max_pages]

            return [
                self.create_document(
                    content=doc.page_content,
                    url=doc.metadata.get("source", self.source.url),
                    loader_name="recursive"
                )
                for doc in raw_documents
            ]
        except Exception as e:
            logger.error(f"Recursive load error for {self.source.url}: {e}")
            return []
