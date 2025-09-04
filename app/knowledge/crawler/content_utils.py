import re
from typing import Dict, Set

from bs4 import BeautifulSoup


class ContentProcessor:
    """Handles HTML content processing and text extraction."""
    
    WHITESPACE_PATTERN = re.compile(r'\n\n+')
    
    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'DNT': '1'
    }

    @classmethod
    def get_headers(cls) -> Dict[str, str]:
        """Get enhanced headers for web requests."""
        headers = cls.DEFAULT_HEADERS.copy()
        headers['Referer'] = 'https://www.google.com/'

        return headers

    @classmethod
    def extract_clean_text(cls, html: str) -> str:
        """Extract and clean text content from HTML."""
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text()
        return cls.WHITESPACE_PATTERN.sub('\n\n', text).strip()


class UrlFilter:
    """Handles URL filtering and exclusion logic."""
    
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

    DEFAULT_EXCLUDE_DIRS = [
        'css', 'js', 'javascript', 'static', 'assets', 'media',
        'images', 'img', 'fonts', 'api', 'wp-json', 'wp-content',
        'wp-includes', 'admin', 'wp-admin', 'oembed', 'feed', 'rss',
        'sites/default/files/css', 'sites/default/files/js',
        'files/css', 'files/js'
    ]

    @classmethod
    def should_exclude_url(cls, url: str) -> bool:
        """Determine if URL should be excluded."""
        url_lower = url.lower()
        url_path = url.split('?')[0].split('#')[0]
        
        if any(url_path.endswith(ext) for ext in cls.EXCLUDED_EXTENSIONS):
            return True
        
        return any(pattern in url_lower for pattern in cls.EXCLUDED_PATH_PATTERNS)

    @classmethod
    def build_exclude_dirs(cls, source) -> list[str]:
        """Build comprehensive list of directories to exclude."""
        exclude_dirs = cls.DEFAULT_EXCLUDE_DIRS.copy()

        if source.exclude_path_patterns:
            custom_patterns = [
                pattern.strip()
                for pattern in source.exclude_path_patterns.split(',')
                if pattern.strip()
            ]
            exclude_dirs.extend(custom_patterns)

        return exclude_dirs
