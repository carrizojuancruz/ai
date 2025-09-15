import pytest
from unittest.mock import patch

from app.knowledge.crawler.service import CrawlerService


@pytest.fixture
def crawler_service():
    return CrawlerService()


class TestCrawlerService:

    @pytest.mark.asyncio
    async def test_crawl_source_success(self, crawler_service, sample_source):
        from langchain_core.documents import Document

        mock_documents = [
            Document(
                page_content="Sample financial content about investments",
                metadata={"source": sample_source.url, "title": "Finance Guide"}
            )
        ]

        with patch.object(crawler_service, '_load_documents') as mock_load:
            mock_load.return_value = mock_documents

            result = await crawler_service.crawl_source(sample_source)

            assert result["documents_loaded"] == 1
            assert result["source_url"] == sample_source.url
            assert "Successfully loaded" in result["message"]
            mock_load.assert_called_once_with(sample_source)

    @pytest.mark.asyncio
    async def test_crawl_source_failure(self, crawler_service, sample_source):
        with patch.object(crawler_service, '_load_documents') as mock_load:
            mock_load.side_effect = Exception("Network connection failed")

            result = await crawler_service.crawl_source(sample_source)

            assert result["documents_loaded"] == 0
            assert "error" in result
            assert "Failed to crawl source" in result["message"]

    def test_get_loader_selection(self, crawler_service, sample_source):
        pdf_source = sample_source.model_copy()
        pdf_source.url = "https://example.com/document.pdf"
        loader = crawler_service._get_loader(pdf_source, "single")
        assert loader.__class__.__name__ == "PDFLoader"

        loader = crawler_service._get_loader(sample_source, "single")
        assert loader.__class__.__name__ == "SinglePageLoader"

        loader = crawler_service._get_loader(sample_source, "recursive")
        assert loader.__class__.__name__ == "RecursiveLoader"

    def test_has_corrupted_content_detection(self, crawler_service):
        from langchain_core.documents import Document

        corrupted_doc = Document(
            page_content="Normal text \x00\x01\x02 binary content \xFF\xFE",
            metadata={}
        )
        normal_doc = Document(
            page_content="This is normal text content without binary characters.",
            metadata={}
        )

        assert crawler_service._has_corrupted_content([corrupted_doc]) is True
        assert crawler_service._has_corrupted_content([normal_doc]) is False
        assert crawler_service._has_corrupted_content([]) is False
