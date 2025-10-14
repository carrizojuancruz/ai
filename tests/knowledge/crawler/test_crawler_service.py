from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.documents import Document

from app.knowledge.crawler.service import CrawlerService


@pytest.mark.unit
class TestCrawlerService:

    @pytest.fixture
    def mock_config(self, mocker):
        mock = mocker.patch('app.knowledge.crawler.service.config')
        mock.CRAWL_TYPE = "recursive"
        mock.CRAWL_TIMEOUT = 30
        mock.MAX_DOCUMENTS_PER_SOURCE = 1000
        return mock

    @pytest.fixture
    def crawler_service(self, mock_config):
        return CrawlerService()

    def test_pdf_loader_selected_for_pdf_url(self, crawler_service, mocker, sample_source):
        sample_source.url = "https://example.com/document.pdf"
        mock_loader = mocker.patch('app.knowledge.crawler.service.PDFLoader')
        mock_instance = MagicMock()
        mock_instance.load_documents.return_value = []
        mock_loader.return_value = mock_instance

        asyncio_run = AsyncMock()
        mocker.patch('asyncio.run', asyncio_run)

        mock_loader.assert_not_called()

    @pytest.mark.asyncio
    async def test_crawl_source_success(self, crawler_service, sample_source, sample_documents, mocker):
        mock_loader = mocker.patch('app.knowledge.crawler.service.RecursiveLoader')
        mock_instance = AsyncMock()
        mock_instance.load_documents.return_value = sample_documents
        mock_loader.return_value = mock_instance

        result = await crawler_service.crawl_source(sample_source)

        assert result["documents"] == sample_documents
        assert result["documents_loaded"] == len(sample_documents)

    @pytest.mark.asyncio
    async def test_crawl_source_empty_results(self, crawler_service, sample_source, mocker):
        mock_loader = mocker.patch('app.knowledge.crawler.service.RecursiveLoader')
        mock_instance = AsyncMock()
        mock_instance.load_documents.return_value = []
        mock_loader.return_value = mock_instance

        result = await crawler_service.crawl_source(sample_source)

        assert result["documents"] == []
        assert result["documents_loaded"] == 0

    @pytest.mark.asyncio
    async def test_filter_documents_excludes_unwanted_urls(self, crawler_service):
        docs = [
            Document(page_content="Content", metadata={"source": "https://example.com/page.html"}),
            Document(page_content="Style", metadata={"source": "https://example.com/style.css"}),
            Document(page_content="Script", metadata={"source": "https://example.com/app.js"}),
            Document(page_content="Image", metadata={"source": "https://example.com/img.png"})
        ]

        filtered = crawler_service._filter_documents(docs)

        assert len(filtered) == 1
        assert "page.html" in filtered[0].metadata["source"]

    @pytest.mark.asyncio
    async def test_filter_documents_keeps_valid_content(self, crawler_service):
        docs = [
            Document(page_content="About", metadata={"source": "https://example.com/about"}),
            Document(page_content="Blog", metadata={"source": "https://example.com/blog/post"}),
            Document(page_content="Product", metadata={"source": "https://example.com/products/item-1"})
        ]

        filtered = crawler_service._filter_documents(docs)

        assert len(filtered) == 3

    @pytest.mark.asyncio
    async def test_crawl_source_exception_handling(self, crawler_service, sample_source, mocker):
        mocker.patch.object(
            crawler_service,
            '_load_documents',
            side_effect=Exception("Load failed")
        )

        result = await crawler_service.crawl_source(sample_source)

        assert result["documents"] == []
        assert result["documents_loaded"] == 0
        assert "Failed to crawl source" in result["message"]
        assert result["error"] == "Load failed"

    def test_has_corrupted_content_true_with_binary_chars(self, crawler_service):
        docs = [
            Document(page_content="Normal text content", metadata={}),
            Document(page_content="Content with \x00\x01\x02 binary chars", metadata={})
        ]

        result = crawler_service._has_corrupted_content(docs)

        assert result is True

    def test_has_corrupted_content_false_clean_content(self, crawler_service):
        docs = [
            Document(page_content="Normal text content", metadata={}),
            Document(page_content="More normal content", metadata={})
        ]

        result = crawler_service._has_corrupted_content(docs)

        assert result is False

    def test_has_corrupted_content_false_empty_content(self, crawler_service):
        docs = [
            Document(page_content="", metadata={}),
            Document(page_content="Short", metadata={})
        ]

        result = crawler_service._has_corrupted_content(docs)

        assert result is False

    def test_get_loader_pdf_url(self, crawler_service, sample_source, mocker):
        sample_source.url = "https://example.com/document.pdf"
        mock_pdf_loader = mocker.patch('app.knowledge.crawler.service.PDFLoader')

        crawler_service._get_loader(sample_source, "recursive")

        mock_pdf_loader.assert_called_once_with(source=sample_source)

    def test_get_loader_single_crawl_type(self, crawler_service, sample_source, mocker):
        mock_single_loader = mocker.patch('app.knowledge.crawler.service.SinglePageLoader')

        crawler_service._get_loader(sample_source, "single")

        mock_single_loader.assert_called_once_with(source=sample_source)

    def test_get_loader_sitemap_crawl_type(self, crawler_service, sample_source, mocker):
        sample_source.total_max_pages = 50
        mock_sitemap_loader = mocker.patch('app.knowledge.crawler.service.SitemapLoader')

        crawler_service._get_loader(sample_source, "sitemap")

        mock_sitemap_loader.assert_called_once_with(source=sample_source, max_pages=50)

    def test_get_loader_recursive_crawl_type(self, crawler_service, sample_source, mocker):
        sample_source.total_max_pages = 100
        sample_source.recursion_depth = 3
        mock_recursive_loader = mocker.patch('app.knowledge.crawler.service.RecursiveLoader')

        crawler_service._get_loader(sample_source, "recursive")

        mock_recursive_loader.assert_called_once_with(
            source=sample_source,
            max_pages=100,
            max_depth=3
        )

    @pytest.mark.asyncio
    async def test_load_documents_recursive_success(self, crawler_service, sample_source, sample_documents, mocker):
        mock_loader = mocker.patch('app.knowledge.crawler.service.RecursiveLoader')
        mock_instance = AsyncMock()
        mock_instance.load_documents.return_value = sample_documents
        mock_loader.return_value = mock_instance

        mocker.patch.object(crawler_service, '_has_corrupted_content', return_value=False)
        mocker.patch.object(crawler_service, '_filter_documents', return_value=sample_documents)

        result = await crawler_service._load_documents(sample_source)

        assert result == sample_documents
        mock_loader.assert_called_once_with(
            source=sample_source,
            max_pages=sample_source.total_max_pages,
            max_depth=sample_source.recursion_depth
        )

    @pytest.mark.asyncio
    async def test_load_documents_corrupted_content_fallback(self, crawler_service, sample_source, sample_documents, mocker):
        mock_recursive_loader = mocker.patch('app.knowledge.crawler.service.RecursiveLoader')
        mock_recursive_instance = AsyncMock()
        mock_recursive_instance.load_documents.return_value = sample_documents
        mock_recursive_loader.return_value = mock_recursive_instance

        mock_single_loader = mocker.patch('app.knowledge.crawler.service.SinglePageLoader')
        mock_single_instance = AsyncMock()
        mock_single_instance.load_documents.return_value = sample_documents
        mock_single_loader.return_value = mock_single_instance

        mocker.patch.object(crawler_service, '_has_corrupted_content', return_value=True)
        mocker.patch.object(crawler_service, '_filter_documents', return_value=sample_documents)

        result = await crawler_service._load_documents(sample_source)

        assert result == sample_documents
        mock_recursive_loader.assert_called_once()
        mock_single_loader.assert_called_once_with(source=sample_source)

    @pytest.mark.asyncio
    async def test_load_documents_javascript_fallback(self, crawler_service, sample_source, sample_documents, mocker):
        mock_recursive_loader = mocker.patch('app.knowledge.crawler.service.RecursiveLoader')
        mock_recursive_instance = AsyncMock()
        mock_recursive_instance.load_documents.return_value = sample_documents
        mock_recursive_loader.return_value = mock_recursive_instance

        mock_single_loader = mocker.patch('app.knowledge.crawler.service.SinglePageLoader')
        mock_single_instance = AsyncMock()
        mock_single_instance.load_documents.return_value = sample_documents
        mock_single_loader.return_value = mock_single_instance

        mocker.patch.object(crawler_service, '_has_corrupted_content', return_value=False)
        mocker.patch('app.knowledge.crawler.service.JavaScriptDetector.needs_javascript', return_value=True)
        mocker.patch.object(crawler_service, '_filter_documents', return_value=sample_documents)

        result = await crawler_service._load_documents(sample_source)

        assert result == sample_documents
        mock_recursive_loader.assert_called_once()
        mock_single_loader.assert_called_once_with(source=sample_source)

    @pytest.mark.asyncio
    async def test_load_documents_loader_error_fallback(self, crawler_service, sample_source, sample_documents, mocker):
        mock_recursive_loader = mocker.patch('app.knowledge.crawler.service.RecursiveLoader')
        mock_recursive_instance = AsyncMock()
        mock_recursive_instance.load_documents.side_effect = Exception("Loader failed")
        mock_recursive_loader.return_value = mock_recursive_instance

        mock_single_loader = mocker.patch('app.knowledge.crawler.service.SinglePageLoader')
        mock_single_instance = AsyncMock()
        mock_single_instance.load_documents.return_value = sample_documents
        mock_single_loader.return_value = mock_single_instance

        result = await crawler_service._load_documents(sample_source)

        assert result == sample_documents
        mock_recursive_loader.assert_called_once()
        mock_single_loader.assert_called_once_with(source=sample_source)
