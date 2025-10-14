from unittest.mock import patch

import pytest
from langchain_core.documents import Document

from app.knowledge.crawler.loaders.base_loader import BaseLoader


class ConcreteLoader(BaseLoader):

    async def load_documents(self):
        return []


@pytest.mark.unit
class TestBaseLoader:

    @pytest.fixture
    def base_loader(self, sample_source):
        return ConcreteLoader(sample_source)

    def test_clean_content(self, base_loader):
        with patch(
            'app.knowledge.crawler.loaders.base_loader.ContentProcessor.extract_clean_text'
        ) as mock_processor:
            mock_processor.return_value = "Clean text"

            result = base_loader.clean_content("<html><body>Test</body></html>")

            mock_processor.assert_called_once()
            assert result == "Clean text"

    def test_create_document(self, base_loader):
        doc = base_loader.create_document(
            "Test content",
            "https://example.com/page",
            "ConcreteLoader",
            title="Test Page"
        )

        assert isinstance(doc, Document)
        assert doc.page_content == "Test content"
        assert doc.metadata["source"] == "https://example.com/page"
        assert doc.metadata["title"] == "Test Page"
        assert doc.metadata["loader"] == "ConcreteLoader"

    def test_create_document_extra_metadata(self, base_loader):
        doc = base_loader.create_document(
            "Content",
            "https://example.com",
            "ConcreteLoader",
            custom_field="custom_value"
        )

        assert doc.metadata["custom_field"] == "custom_value"

    def test_get_headers(self, base_loader):
        with patch(
            'app.knowledge.crawler.loaders.base_loader.ContentProcessor.get_headers'
        ) as mock_processor:
            mock_processor.return_value = {"User-Agent": "Test"}

            headers = base_loader.get_headers()

            mock_processor.assert_called_once()
            assert headers["User-Agent"] == "Test"
