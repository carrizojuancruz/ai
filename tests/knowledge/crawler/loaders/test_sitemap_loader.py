import pytest
from langchain_core.documents import Document

from app.knowledge.crawler.loaders.sitemap_loader import SitemapLoader


@pytest.mark.unit
class TestSitemapLoader:

    @pytest.fixture
    def sitemap_loader(self, sample_source):
        sample_source.url = "https://example.com/sitemap.xml"
        return SitemapLoader(sample_source)

    @pytest.fixture
    def mock_langchain_loader(self, mocker):
        mock = mocker.patch(
            'app.knowledge.crawler.loaders.sitemap_loader.LangchainSitemapLoader'
        )
        mock_instance = mocker.MagicMock()
        mock_instance.load.return_value = []
        mock.return_value = mock_instance
        return mock_instance

    @pytest.mark.asyncio
    async def test_load_documents_success(self, sitemap_loader, mock_langchain_loader, sample_documents):
        mock_langchain_loader.load.return_value = sample_documents

        docs = await sitemap_loader.load_documents()

        assert len(docs) == len(sample_documents)

    @pytest.mark.asyncio
    async def test_load_documents_respects_max_pages(self, sitemap_loader, mock_langchain_loader):
        docs = [
            Document(page_content=f"Content {i}", metadata={})
            for i in range(50)
        ]
        mock_langchain_loader.load.return_value = docs
        sitemap_loader.source.total_max_pages = 20

        result = await sitemap_loader.load_documents()

        assert len(result) <= 20

    @pytest.mark.asyncio
    async def test_sitemap_filter_function(self, sitemap_loader, mock_langchain_loader, mocker):
        mock_filter = mocker.patch(
            'app.knowledge.crawler.loaders.sitemap_loader.UrlFilter.should_exclude_url'
        )
        mock_filter.return_value = False

        await sitemap_loader.load_documents()

        mock_langchain_loader.load.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_documents_exception_handling(self, sitemap_loader, mock_langchain_loader):
        mock_langchain_loader.load.side_effect = Exception("Sitemap error")

        result = await sitemap_loader.load_documents()

        assert result == []
