import pytest
from langchain_core.documents import Document

from app.knowledge.crawler.loaders.single_page_loader import SinglePageLoader


@pytest.mark.unit
class TestSinglePageLoader:

    @pytest.fixture
    def single_page_loader(self, sample_source):
        return SinglePageLoader(sample_source)

    @pytest.mark.asyncio
    async def test_load_documents_success(self, single_page_loader, mock_playwright):
        docs = await single_page_loader.load_documents()

        assert len(docs) > 0
        assert isinstance(docs[0], Document)
        mock_playwright.goto.assert_called()
        mock_playwright.set_extra_http_headers.assert_called()
        mock_playwright.wait_for_timeout.assert_called()

    @pytest.mark.asyncio
    async def test_load_documents_playwright_exception(self, single_page_loader, mock_playwright):
        mock_playwright.goto.side_effect = Exception("Navigation error")

        result = await single_page_loader.load_documents()

        assert result == []
