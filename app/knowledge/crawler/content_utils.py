import logging
import re
from typing import Dict, List, Set

from bs4 import BeautifulSoup
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class ContentProcessor:
    WHITESPACE_PATTERN = re.compile(r'\n\n+')
    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Cache-Control': 'max-age=0',
        'Sec-Ch-Ua': '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1'
    }

    @classmethod
    def get_headers(cls) -> Dict[str, str]:
        headers = cls.DEFAULT_HEADERS.copy()
        headers['Referer'] = 'https://www.google.com/'
        return headers

    @classmethod
    def extract_clean_text(cls, html: str) -> str:
        if isinstance(html, bytes):
            html = html.decode('utf-8', errors='ignore')
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text()
        return cls.WHITESPACE_PATTERN.sub('\n\n', text).strip()
class UrlFilter:
    EXCLUDED_EXTENSIONS: Set[str] = {
        '.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
        '.woff', '.woff2', '.ttf', '.eot', '.zip', '.exe', '.dmg',
        '.mp4', '.mp3', '.avi', '.mov', '.webm', '.ogg', '.wav'
    }

    EXCLUDED_PATH_PATTERNS: Set[str] = {
        '/css/', '/js/', '/static/', '/assets/', '/media/', '/images/',
        '/img/', '/fonts/', '/api/', '/wp-json/', '/wp-content/',
        '/wp-includes/', '/admin/', '/wp-admin/', '/feed/', '/rss/',
        '/sitemap.xml', '/robots.txt'
    }

    DEFAULT_EXCLUDE_DIRS = [
        'css', 'js', 'static', 'assets', 'media', 'images', 'img',
        'fonts', 'api', 'wp-json', 'wp-content', 'wp-includes',
        'admin', 'wp-admin', 'feed', 'rss'
    ]

    @classmethod
    def should_exclude_url(cls, url: str) -> bool:
        url_lower = url.lower()
        url_path = url.split('?')[0].split('#')[0]

        if any(url_path.lower().endswith(ext) for ext in cls.EXCLUDED_EXTENSIONS):
            return True
        return any(pattern in url_lower for pattern in cls.EXCLUDED_PATH_PATTERNS)

    @classmethod
    def build_exclude_dirs(cls, source) -> list[str]:
        exclude_dirs = cls.DEFAULT_EXCLUDE_DIRS.copy()
        if source.exclude_path_patterns:
            custom_patterns = [
                pattern.strip()
                for pattern in source.exclude_path_patterns.split(',')
                if pattern.strip()
            ]
            exclude_dirs.extend(custom_patterns)
        return exclude_dirs


class JavaScriptDetector:
    JS_PATTERNS = [
        r'javascript\s+is\s+required', r'please\s+enable\s+javascript',
        r'enable\s+javascript', r'javascript\s+disabled',
        r'requires\s+javascript', r'<noscript>', r'document\.write',
        r'loading\.\.\.', r'react-root', r'vue-app', r'ng-app'
    ]

    CLOUDFLARE_PATTERNS = [
        r'attention required.*cloudflare', r'cloudflare ray id',
        r'you have been blocked', r'please enable cookies',
        r'checking your browser', r'performance & security by cloudflare'
    ]

    COMPILED_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in JS_PATTERNS]
    COMPILED_CF_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in CLOUDFLARE_PATTERNS]

    @classmethod
    def needs_javascript(cls, documents: List[Document]) -> bool:
        if not documents:
            return False

        all_content = ' '.join(doc.page_content for doc in documents)

        if cls.is_cloudflare_blocked(all_content):
            return True

        if any(pattern.search(all_content) for pattern in cls.COMPILED_PATTERNS):
            return True

        content_stripped = all_content.strip()
        if len(content_stripped) < 100:
            return True

        script_count = all_content.lower().count('<script')
        content_words = len(content_stripped.split())

        if script_count > 0 and content_words < 50:
            return True

        text_content = re.sub(r'<[^>]+>', '', content_stripped)
        text_content = re.sub(r'\s+', ' ', text_content).strip()

        return len(text_content) < 200

    @classmethod
    def is_cloudflare_blocked(cls, content: str) -> bool:
        return any(pattern.search(content) for pattern in cls.COMPILED_CF_PATTERNS)
