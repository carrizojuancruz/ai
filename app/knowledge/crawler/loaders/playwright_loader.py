import asyncio
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import List

from langchain_core.documents import Document
from playwright.sync_api import sync_playwright

from .base_loader import BaseLoader

logger = logging.getLogger(__name__)


class PlaywrightLoader(BaseLoader):

    def _load_sync(self) -> List[Document]:
        documents = []

        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                page.set_extra_http_headers(self.get_headers())

                try:
                    page.goto(self.source.url, wait_until="networkidle", timeout=30000)
                    page.wait_for_timeout(2000)
                    html_content = page.content()

                    clean_content = self.clean_content(html_content)

                    document = self.create_document(
                        content=clean_content,
                        url=self.source.url,
                        loader_name="playwright"
                    )
                    documents.append(document)

                except Exception as e:
                    logger.error(f"Error loading {self.source.url} with Playwright: {e}")

                browser.close()

        except Exception as e:
            logger.error(f"Playwright execution failed: {e}")
        finally:
            loop.close()

        return documents

    async def load_documents(self) -> List[Document]:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            documents = await loop.run_in_executor(executor, self._load_sync)
        return documents
