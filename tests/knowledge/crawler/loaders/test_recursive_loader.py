import pytest
from langchain_core.documents import Document

from app.knowledge.crawler.loaders.recursive_loader import RecursiveLoader


@pytest.mark.unit
class TestRecursiveLoader:

    @pytest.fixture
    def recursive_loader(self, sample_source):
        return RecursiveLoader(sample_source)

    @pytest.fixture
    def mock_langchain_loader(self, mocker):
        mock = mocker.patch(
            'app.knowledge.crawler.loaders.recursive_loader.RecursiveUrlLoader'
        )
        mock_instance = mocker.MagicMock()
        mock_instance.load.return_value = []
        mock.return_value = mock_instance
        return mock_instance

    @pytest.mark.asyncio
    async def test_load_documents_success(self, recursive_loader, mock_langchain_loader, sample_documents):
        mock_langchain_loader.load.return_value = sample_documents

        docs = await recursive_loader.load_documents()

        assert len(docs) == len(sample_documents)

    @pytest.mark.asyncio
    async def test_load_documents_respects_max_pages(self, recursive_loader, mock_langchain_loader, mocker):
        docs = [
            Document(page_content=f"Content {i}", metadata={})
            for i in range(100)
        ]
        mock_langchain_loader.load.return_value = docs
        recursive_loader.source.total_max_pages = 10

        result = await recursive_loader.load_documents()

        assert len(result) <= 10

    @pytest.mark.asyncio
    async def test_load_documents_exception_handling(self, recursive_loader, mock_langchain_loader):
        mock_langchain_loader.load.side_effect = Exception("Crawl error")

        result = await recursive_loader.load_documents()

        assert result == []
