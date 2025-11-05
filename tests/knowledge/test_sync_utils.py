"""Unit tests for knowledge sync utilities."""

from app.knowledge.utils import (
    generate_source_id,
    is_crawlable_url,
    normalize_url,
    validate_url,
)


def test_normalize_url_removes_trailing_slash():
    """Test URL normalization removes trailing slashes."""
    assert normalize_url("https://example.com/") == "https://example.com"
    assert normalize_url("https://example.com/page/") == "https://example.com/page"


def test_normalize_url_removes_query_params():
    """Test URL normalization removes query parameters."""
    assert normalize_url("https://example.com?q=test") == "https://example.com"
    assert normalize_url("https://example.com/page?id=123&ref=abc") == "https://example.com/page"


def test_normalize_url_removes_fragment():
    """Test URL normalization removes fragments."""
    assert normalize_url("https://example.com#section") == "https://example.com"
    assert normalize_url("https://example.com/page#top") == "https://example.com/page"


def test_normalize_url_complete():
    """Test complete URL normalization with all components."""
    url = "https://example.com/page/?q=test&ref=link#section"
    expected = "https://example.com/page"
    assert normalize_url(url) == expected


def test_validate_url_valid():
    """Test validation accepts valid URLs."""
    is_valid, error = validate_url("https://example.com")
    assert is_valid is True
    assert error == ""

    is_valid, error = validate_url("http://example.com/path")
    assert is_valid is True
    assert error == ""


def test_validate_url_invalid_scheme():
    """Test validation rejects invalid schemes."""
    is_valid, error = validate_url("ftp://example.com")
    assert is_valid is False
    assert "http or https" in error.lower()


def test_validate_url_no_scheme():
    """Test validation rejects URLs without scheme."""
    is_valid, error = validate_url("example.com")
    assert is_valid is False
    assert "protocol" in error.lower()


def test_validate_url_no_domain():
    """Test validation rejects URLs without domain."""
    is_valid, error = validate_url("https://")
    assert is_valid is False
    assert "domain" in error.lower()


def test_validate_url_localhost():
    """Test validation rejects localhost URLs."""
    is_valid, error = validate_url("http://localhost:8000")
    assert is_valid is False
    assert "localhost" in error.lower()

    is_valid, error = validate_url("http://127.0.0.1")
    assert is_valid is False
    assert "localhost" in error.lower()


def test_is_crawlable_url_html():
    """Test crawlability check accepts HTML pages."""
    assert is_crawlable_url("https://example.com/page.html") is True
    assert is_crawlable_url("https://example.com/docs/guide") is True
    assert is_crawlable_url("https://example.com/") is True


def test_is_crawlable_url_images():
    """Test crawlability check rejects image files."""
    assert is_crawlable_url("https://example.com/logo.png") is False
    assert is_crawlable_url("https://example.com/photo.jpg") is False
    assert is_crawlable_url("https://example.com/icon.svg") is False
    assert is_crawlable_url("https://example.com/image.gif") is False


def test_is_crawlable_url_assets():
    """Test crawlability check rejects asset files."""
    assert is_crawlable_url("https://example.com/style.css") is False
    assert is_crawlable_url("https://example.com/app.js") is False
    assert is_crawlable_url("https://example.com/font.woff2") is False
    assert is_crawlable_url("https://example.com/font.ttf") is False


def test_is_crawlable_url_media():
    """Test crawlability check rejects media files."""
    assert is_crawlable_url("https://example.com/video.mp4") is False
    assert is_crawlable_url("https://example.com/audio.mp3") is False
    assert is_crawlable_url("https://example.com/movie.avi") is False


def test_is_crawlable_url_archives():
    """Test crawlability check rejects archive files."""
    assert is_crawlable_url("https://example.com/archive.zip") is False
    assert is_crawlable_url("https://example.com/file.tar") is False
    assert is_crawlable_url("https://example.com/data.gz") is False


def test_generate_source_id_deterministic():
    """Test source ID generation is deterministic."""
    url = "https://example.com"
    id1 = generate_source_id(url)
    id2 = generate_source_id(url)
    assert id1 == id2


def test_generate_source_id_different_urls():
    """Test different URLs generate different IDs."""
    id1 = generate_source_id("https://example.com")
    id2 = generate_source_id("https://different.com")
    assert id1 != id2


def test_generate_source_id_length():
    """Test source ID has correct length."""
    source_id = generate_source_id("https://example.com")
    assert len(source_id) == 16


def test_generate_source_id_normalizes():
    """Test source ID generation normalizes URLs first."""
    id1 = generate_source_id("https://example.com/page")
    id2 = generate_source_id("https://example.com/page/")
    id3 = generate_source_id("https://example.com/page?q=test")
    id4 = generate_source_id("https://example.com/page#section")
    # All should be the same after normalization
    assert id1 == id2 == id3 == id4


def test_normalize_url_handles_whitespace():
    """Test URL normalization handles whitespace."""
    assert normalize_url("  https://example.com  ") == "https://example.com"
    assert normalize_url("\thttps://example.com\n") == "https://example.com"


def test_normalize_url_empty_string():
    """Test URL normalization with empty string."""
    assert normalize_url("") == ""
    assert normalize_url("   ") == ""


def test_validate_url_empty_string():
    """Test validation rejects empty URLs."""
    is_valid, error = validate_url("")
    assert is_valid is False
    assert "protocol" in error.lower()


def test_validate_url_malformed():
    """Test validation rejects malformed URLs."""
    is_valid, error = validate_url("ht!tp://example.com")
    assert is_valid is False


def test_is_crawlable_url_case_insensitive():
    """Test crawlability check is case-insensitive."""
    assert is_crawlable_url("https://example.com/IMAGE.PNG") is False
    assert is_crawlable_url("https://example.com/STYLE.CSS") is False


def test_generate_source_id_empty_url():
    """Test source ID generation with empty URL."""
    source_id = generate_source_id("")
    assert len(source_id) == 16
    assert isinstance(source_id, str)
