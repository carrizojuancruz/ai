"""Utility functions for knowledge base operations."""

import hashlib
import logging
from typing import Tuple
from urllib.parse import urlparse, urlunparse

from .internal_sections import INTERNAL_S3_SECTIONS, INTERNAL_URL_SECTIONS

logger = logging.getLogger(__name__)

def normalize_url(url: str) -> str:
    """Normalize URL by removing trailing slashes, fragments, and query params."""
    parsed = urlparse(url.strip())

    normalized = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path.rstrip('/'),
        '',
        '',
        ''
    ))

    return normalized


def validate_url(url: str) -> Tuple[bool, str]:
    """Validate if URL is properly formatted and crawlable."""
    try:
        parsed = urlparse(url)

        if not parsed.scheme:
            return False, "URL must include protocol (http or https)"

        if parsed.scheme not in ['http', 'https']:
            return False, "URL must use http or https protocol"

        if not parsed.netloc:
            return False, "URL must include domain"

        if 'localhost' in parsed.netloc or '127.0.0.1' in parsed.netloc:
            return False, "Cannot crawl localhost URLs"

        return True, ""

    except Exception as e:
        return False, f"Invalid URL format: {str(e)}"


def is_crawlable_url(url: str) -> bool:
    """Check if URL is crawlable (not an asset file)."""
    asset_extensions = {
        '.jpg', '.jpeg', '.png', '.gif', '.svg', '.ico',
        '.mp4', '.mp3', '.avi', '.mov', '.wav',
        '.zip', '.tar', '.gz', '.rar',
        '.exe', '.dmg', '.pkg',
        '.css', '.js', '.woff', '.woff2', '.ttf', '.eot'
    }

    parsed = urlparse(url.lower())
    path = parsed.path
    return not any(path.endswith(ext) for ext in asset_extensions)


def generate_source_id(url: str) -> str:
    """Generate deterministic source ID from URL."""
    normalized = normalize_url(url)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def get_subcategory_for_url(url: str) -> str:
    """Get subcategory if URL contains any configured article ID.

    Used for web-crawled help center articles.

    Args:
        url: URL to check for article ID patterns

    Returns:
        Subcategory name if matched, empty string otherwise

    """
    if not url:
        return ""

    for subcategory, article_ids in INTERNAL_URL_SECTIONS.items():
        for article_id in article_ids:
            if article_id in url:
                return subcategory

    return ""


def get_subcategory_for_s3_key(s3_key: str) -> str:
    """Get subcategory if S3 key starts with any configured folder prefix."""
    if not s3_key:
        return ""

    s3_key_lower = s3_key.lower()

    for subcategory, folder_prefixes in INTERNAL_S3_SECTIONS.items():
        if any(s3_key_lower.startswith(prefix.lower()) for prefix in folder_prefixes):
            return subcategory

    return ""
