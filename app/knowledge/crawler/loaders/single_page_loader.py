import asyncio
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import List

from langchain_core.documents import Document
from playwright.sync_api import sync_playwright

from .base_loader import BaseLoader

logger = logging.getLogger(__name__)


class SinglePageLoader(BaseLoader):

    def _load_sync(self) -> List[Document]:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--disable-web-security',
                        '--disable-features=VizDisplayCompositor'
                    ]
                )
                page = browser.new_page()

                page.set_extra_http_headers(self.get_headers())
                page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

                try:
                    page.goto(self.source.url, wait_until="networkidle", timeout=30000)
                    page.wait_for_timeout(2000)
                    html_content = page.content()
                    clean_content = self.clean_content(html_content)

                    return [self.create_document(
                        content=clean_content,
                        url=self.source.url,
                        loader_name="single_page"
                    )]
                except Exception as e:
                    logger.error(f"Error loading {self.source.url} with Playwright: {e}")
                    return []
                finally:
                    browser.close()
        except Exception as e:
            logger.error(f"Playwright execution failed: {e}")
            return []
        finally:
            loop.close()

    async def load_documents(self) -> List[Document]:
        try:
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=1) as executor:
                return await loop.run_in_executor(executor, self._load_sync)
        except Exception as e:
            logger.error(f"SinglePageLoader failed for {self.source.url}: {e}")
            return []
