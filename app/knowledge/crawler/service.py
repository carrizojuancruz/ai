import logging
import re
import ssl
from typing import Any, Dict, List, Set

from bs4 import BeautifulSoup
from langchain_community.document_loaders import RecursiveUrlLoader, SitemapLoader
from langchain_core.documents import Document

from app.core.config import config
from app.knowledge.models import Source

logger = logging.getLogger(__name__)


class CrawlerService:
    """Professional web crawler service with advanced filtering and content extraction."""

    EXCLUDED_EXTENSIONS: Set[str] = {
        '.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
        '.woff', '.woff2', '.ttf', '.eot', '.pdf', '.zip', '.exe', '.dmg',
        '.mp4', '.mp3', '.avi', '.mov', '.webm', '.ogg', '.wav'
    }

    EXCLUDED_PATH_PATTERNS: Set[str] = {
        '/css/', '/js/', '/javascript/', '/static/', '/assets/', '/media/',
        '/images/', '/img/', '/fonts/', '/api/', '/wp-json/', '/wp-content/',
        '/wp-includes/', '/admin/', '/wp-admin/', '/oembed/', '/feed/',
        '/rss/', '/atom/', '/sitemap.xml', '/robots.txt',
        'sites/default/files/css', 'sites/default/files/js',
        'files/css', 'files/js'
    }

    DEFAULT_EXCLUDE_DIRS: List[str] = [
        'css', 'js', 'javascript', 'static', 'assets', 'media',
        'images', 'img', 'fonts', 'api', 'wp-json', 'wp-content',
        'wp-includes', 'admin', 'wp-admin', 'oembed', 'feed', 'rss',
        'sites/default/files/css', 'sites/default/files/js',
        'files/css', 'files/js'
    ]

    WHITESPACE_PATTERN = re.compile(r'\n\n+')

    DEFAULT_HEADERS = {
        'User-Agent': 'Verde-AI Knowledge Crawler 1.0 (Educational/Research Purpose)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': '*',
        'Accept-Encoding': 'gzip, deflate'
    }

    def __init__(self):
        """Initialize the crawler service with configuration.

        Note: We respect robots.txt and rate limits for ethical crawling.
        SSL bypass is only for technical certificate issues, not security bypass.
        """
        self._config = config
        self.crawl_type = config.CRAWL_TYPE
        self.timeout = config.CRAWL_TIMEOUT

        ssl._create_default_https_context = ssl._create_unverified_context

    @classmethod
    def _extract_clean_text(cls, html: str) -> str:
        """Extract and clean text content from HTML.

        Args:
            html: Raw HTML content

        Returns:
            Cleaned text content with normalized whitespace

        """
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text()
        return cls.WHITESPACE_PATTERN.sub('\n\n', text).strip()

    @classmethod
    def _should_exclude_url(cls, url: str) -> bool:
        """Determine if URL should be excluded based on extension and path patterns.

        Args:
            url: URL to check

        Returns:
            True if URL should be excluded, False otherwise

        """
        url_lower = url.lower()

        url_path = url.split('?')[0].split('#')[0]
        if any(url_path.endswith(ext) for ext in cls.EXCLUDED_EXTENSIONS):
            return True

        return any(pattern in url_lower for pattern in cls.EXCLUDED_PATH_PATTERNS)

    @classmethod
    def _build_exclude_dirs(cls, source: Source) -> List[str]:
        """Build comprehensive list of directories to exclude during crawling.

        Args:
            source: Source configuration with optional custom exclude patterns

        Returns:
            List of directory patterns to exclude

        """
        exclude_dirs = cls.DEFAULT_EXCLUDE_DIRS.copy()

        if source.exclude_path_patterns:
            custom_patterns = [
                pattern.strip()
                for pattern in source.exclude_path_patterns.split(',')
                if pattern.strip()
            ]
            exclude_dirs.extend(custom_patterns)

        return exclude_dirs

    def _filter_documents(self, documents: List[Document]) -> List[Document]:

        filtered_documents = []

        for doc in documents:
            if not hasattr(doc, 'metadata') or 'source' not in doc.metadata:
                filtered_documents.append(doc)
                continue

            source_url = doc.metadata['source']
            if self._should_exclude_url(source_url):
                logger.debug(f"Filtered out asset URL: {source_url}")
                continue

            filtered_documents.append(doc)

        return filtered_documents

    async def crawl_source(self, source: Source) -> Dict[str, Any]:
        try:
            documents = await self._load_documents(source)

            result = {
                "documents": documents,
                "documents_loaded": len(documents),
                "source_url": source.url,
                "message": f"Successfully loaded {len(documents)} documents",
                "crawl_type": self.crawl_type
            }

            logger.debug(f"Crawl completed for {source.url}: {len(documents)} documents loaded")
            return result

        except Exception as e:
            logger.error(f"Error crawling source {source.url}: {e}")
            return {
                "documents": [],
                "documents_loaded": 0,
                "source_url": source.url,
                "message": f"Failed to crawl source: {str(e)}",
                "error": str(e)
            }

    async def _load_documents(self, source: Source) -> List[Document]:

        crawl_type = self.crawl_type.lower()

        if crawl_type == "single":
            return await self._load_single_page(source.url)
        elif crawl_type == "sitemap":
            return await self._load_sitemap(source.url, source.total_max_pages)
        else:
            return await self._load_recursive(source, source.total_max_pages, source.recursion_depth)

    async def _load_recursive(self, source: Source, max_pages: int, max_depth: int) -> List[Document]:

        try:
            exclude_dirs = self._build_exclude_dirs(source)

            loader = RecursiveUrlLoader(
                url=source.url,
                max_depth=max_depth,
                prevent_outside=True,
                timeout=self.timeout,
                exclude_dirs=exclude_dirs,
                extractor=self._extract_clean_text,
                check_response_status=False,
                continue_on_failure=True,
                headers=self.DEFAULT_HEADERS,
                ssl=False
            )

            documents = loader.load()[:max_pages]

            filtered_documents = self._filter_documents(documents)

            return filtered_documents

        except Exception as e:
            logger.error(f"Recursive load error for {source.url}: {e}")
            return []

    async def _load_sitemap(self, url: str, max_pages: int) -> List[Document]:

        try:
            def sitemap_filter(url: str) -> bool:
                return not self._should_exclude_url(url)

            loader = SitemapLoader(
                web_path=url,
                filter_urls=sitemap_filter
            )

            documents = loader.load()[:max_pages]

            return documents

        except Exception as e:
            logger.error(f"Sitemap load error for {url}: {e}")
            return []

    async def _load_single_page(self, url: str) -> List[Document]:

        try:
            loader = RecursiveUrlLoader(
                url=url,
                max_depth=0,
                extractor=self._extract_clean_text,
                timeout=self.timeout,
                check_response_status=False,
                headers=self.DEFAULT_HEADERS,
                ssl=False
            )

            documents = loader.load()

            return documents

        except Exception as e:
            logger.error(f"Single page load error for {url}: {e}")
            return []
