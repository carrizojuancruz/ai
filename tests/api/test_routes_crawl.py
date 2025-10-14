"""Tests for routes_crawl.py - Web crawling endpoints."""

from unittest.mock import MagicMock, patch

from app.knowledge.models import Source


class TestCrawlUrl:
    """Test cases for POST /crawl endpoint."""

    def test_crawl_url_success(self, client, mocker, mock_crawler_service, mock_document_service):
        """
        Test successful crawling validates API contract and data transformation.

        Focuses on:
        - API correctly transforms chunk objects to response format
        - Source model is properly constructed from request URL
        - Response includes all required fields (url, counts, chunks, message)
        """
        test_url = "https://example.com"

        mock_documents = [{"content": "Doc 1"}, {"content": "Doc 2"}]
        mock_chunks = [
            MagicMock(
                page_content="Chunk 1",
                metadata={
                    "section_url": f"{test_url}#section1",
                    "source_url": test_url,
                    "content_hash": "hash1"
                }
            ),
            MagicMock(
                page_content="Chunk 2",
                metadata={
                    "section_url": f"{test_url}#section2",
                    "source_url": test_url,
                    "content_hash": "hash2"
                }
            )
        ]

        mock_crawler_service.crawl_source.return_value = {"documents": mock_documents}
        mock_document_service.split_documents.return_value = mock_chunks

        with patch('app.api.routes_crawl.CrawlerService', return_value=mock_crawler_service), \
             patch('app.api.routes_crawl.DocumentService', return_value=mock_document_service):
            response = client.post("/crawl", json={"url": test_url})

        assert response.status_code == 200
        data = response.json()

        assert "url" in data and data["url"] == test_url
        assert "total_documents" in data and data["total_documents"] == 2
        assert "total_chunks" in data and data["total_chunks"] == 2
        assert "chunks" in data and len(data["chunks"]) == 2
        assert "message" in data and "Successfully crawled" in data["message"]

        assert data["chunks"][0]["content"] == "Chunk 1"
        assert data["chunks"][0]["section_url"] == f"{test_url}#section1"
        assert data["chunks"][1]["content"] == "Chunk 2"

        call_args = mock_crawler_service.crawl_source.call_args[0][0]
        assert isinstance(call_args, Source)
        assert call_args.url == test_url

    def test_crawl_url_no_documents_found(self, client, mocker, mock_crawler_service, mock_document_service):
        """Test crawling when no documents are found."""
        test_url = "https://empty-site.com"

        # Setup mocks - crawler returns empty documents
        mock_crawler_service.crawl_source.return_value = {"documents": []}

        with patch('app.api.routes_crawl.CrawlerService', return_value=mock_crawler_service), \
             patch('app.api.routes_crawl.DocumentService', return_value=mock_document_service):

            response = client.post("/crawl", json={"url": test_url})

        assert response.status_code == 200
        data = response.json()
        assert data["url"] == test_url
        assert data["total_documents"] == 0
        assert data["total_chunks"] == 0
        assert data["chunks"] == []
        assert "No content found" in data["message"]

        # Verify service calls
        mock_crawler_service.crawl_source.assert_called_once()
        mock_document_service.split_documents.assert_not_called()

    def test_crawl_url_crawling_error(self, client, mocker, mock_crawler_service, mock_document_service):
        """Test crawling when crawler service returns an error."""
        test_url = "https://error-site.com"
        error_message = "Failed to fetch content"

        # Setup mocks - crawler returns error
        mock_crawler_service.crawl_source.return_value = {
            "error": True,
            "message": error_message
        }

        with patch('app.api.routes_crawl.CrawlerService', return_value=mock_crawler_service), \
             patch('app.api.routes_crawl.DocumentService', return_value=mock_document_service):

            response = client.post("/crawl", json={"url": test_url})

        assert response.status_code == 400
        data = response.json()
        assert "Crawling failed" in data["detail"]
        assert error_message in data["detail"]

        # Verify service calls
        mock_crawler_service.crawl_source.assert_called_once()
        mock_document_service.split_documents.assert_not_called()

    def test_crawl_url_general_exception(self, client, mocker, mock_crawler_service, mock_document_service):
        """Test crawling when a general exception occurs."""
        test_url = "https://exception-site.com"

        # Setup mocks - crawler raises exception
        mock_crawler_service.crawl_source.side_effect = Exception("Network timeout")

        with patch('app.api.routes_crawl.CrawlerService', return_value=mock_crawler_service), \
             patch('app.api.routes_crawl.DocumentService', return_value=mock_document_service):

            response = client.post("/crawl", json={"url": test_url})

        assert response.status_code == 500
        data = response.json()
        assert "Crawl failed" in data["detail"]
        assert "Network timeout" in data["detail"]

        # Verify service calls
        mock_crawler_service.crawl_source.assert_called_once()

