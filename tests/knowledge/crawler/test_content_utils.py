import pytest
from langchain_core.documents import Document

from app.knowledge.crawler.content_utils import ContentProcessor, JavaScriptDetector, UrlFilter


@pytest.mark.unit
class TestContentProcessor:

    def test_get_headers(self):
        headers = ContentProcessor.get_headers()

        assert isinstance(headers, dict)
        assert "User-Agent" in headers
        assert "Accept" in headers
        assert headers["Referer"] == "https://www.google.com/"

    def test_extract_clean_text_from_html(self):
        html = "<html><head><script>code</script></head><body><p>Test content</p></body></html>"

        text = ContentProcessor.extract_clean_text(html)

        assert "Test content" in text
        assert "<p>" in text or "Test content" in text
        assert "code" not in text

    def test_extract_clean_text_removes_excessive_whitespace(self):
        html = "<html><body><p>Para 1</p>\n\n\n\n<p>Para 2</p></body></html>"

        text = ContentProcessor.extract_clean_text(html)

        assert "\n\n\n\n" not in text

    def test_extract_clean_text_handles_bytes(self):
        html_bytes = b"<html><body>Test content</body></html>"

        text = ContentProcessor.extract_clean_text(html_bytes)

        assert "Test content" in text


@pytest.mark.unit
class TestUrlFilter:

    @pytest.mark.parametrize("url", [
        "https://example.com/style.css",
        "https://example.com/app.js",
        "https://example.com/image.png",
        "https://example.com/image.jpg",
        "https://example.com/icon.svg",
        "https://example.com/font.woff"
    ])
    def test_should_exclude_url_static_resources(self, url):
        assert UrlFilter.should_exclude_url(url) is True

    @pytest.mark.parametrize("url", [
        "https://example.com/css/",
        "https://example.com/js/scripts/",
        "https://example.com/wp-admin/",
        "https://example.com/static/assets/"
    ])
    def test_should_exclude_url_path_patterns(self, url):
        assert UrlFilter.should_exclude_url(url) is True

    @pytest.mark.parametrize("url", [
        "https://example.com/CSS/STYLE.CSS",
        "https://example.com/APP.JS",
        "https://example.com/IMAGE.PNG"
    ])
    def test_should_exclude_url_case_insensitive(self, url):
        assert UrlFilter.should_exclude_url(url) is True

    @pytest.mark.parametrize("url", [
        "https://example.com/about",
        "https://example.com/products/item",
        "https://example.com/blog/post",
        "https://example.com/documentation.pdf"
    ])
    def test_should_not_exclude_valid_pages(self, url):
        assert UrlFilter.should_exclude_url(url) is False


@pytest.mark.unit
class TestJavaScriptDetector:

    def test_needs_javascript_empty_documents(self):
        assert JavaScriptDetector.needs_javascript([]) is False

    @pytest.mark.parametrize("content", [
        "JavaScript is required to view this page",
        "Please enable JavaScript to continue",
        "This site requires JavaScript"
    ])
    def test_needs_javascript_js_required_pattern(self, content):
        docs = [Document(page_content=content, metadata={})]
        assert JavaScriptDetector.needs_javascript(docs) is True

    def test_needs_javascript_noscript_tag(self):
        docs = [Document(page_content="<noscript>Enable JS</noscript>", metadata={})]
        assert JavaScriptDetector.needs_javascript(docs) is True

    def test_needs_javascript_very_short_content(self):
        docs = [Document(page_content="Short", metadata={})]
        assert JavaScriptDetector.needs_javascript(docs) is True

    def test_needs_javascript_valid_content(self):
        content = "This is substantial text content. " * 50
        docs = [Document(page_content=content, metadata={})]
        assert JavaScriptDetector.needs_javascript(docs) is False
