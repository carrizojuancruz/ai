import pytest
from langchain_core.documents import Document

from app.knowledge.crawler.loaders.pdf_loader import PDFLoader


@pytest.mark.unit
class TestPDFLoader:

    @pytest.fixture
    def pdf_loader(self, sample_source):
        sample_source.url = "https://example.com/document.pdf"
        return PDFLoader(sample_source)

    @pytest.fixture
    def mock_pypdf_loader(self, mocker):
        mock = mocker.patch(
            'app.knowledge.crawler.loaders.pdf_loader.PyPDFLoader'
        )
        mock_instance = mocker.MagicMock()
        mock_instance.load.return_value = []
        mock.return_value = mock_instance
        return mock_instance

    @pytest.mark.asyncio
    async def test_load_documents_success(self, pdf_loader, mock_pypdf_loader):
        pdf_docs = [
            Document(page_content=f"Page {i} content", metadata={"page": i})
            for i in range(10)
        ]
        mock_pypdf_loader.load.return_value = pdf_docs

        docs = await pdf_loader.load_documents()

        assert len(docs) == 10
        assert all(isinstance(doc, Document) for doc in docs)

    @pytest.mark.asyncio
    async def test_load_documents_exception_handling(self, pdf_loader, mock_pypdf_loader):
        mock_pypdf_loader.load.side_effect = Exception("PDF parse error")

        result = await pdf_loader.load_documents()

        assert result == []
