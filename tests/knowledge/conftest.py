"""Shared fixtures for knowledge module tests."""

from datetime import UTC, datetime
from typing import List
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.documents import Document

from app.knowledge.models import Source


def pytest_configure(config):
    config.addinivalue_line("markers", "unit: Unit tests (no external dependencies)")
    config.addinivalue_line("markers", "integration: Integration tests (with external dependencies)")
    config.addinivalue_line("markers", "slow: Slow running tests")


@pytest.fixture
def sample_source():
    return Source(
        id="test123",
        name="Test Source",
        url="https://example.com",
        enabled=True,
        type="article",
        category="finance",
        total_max_pages=20,
        recursion_depth=2
    )


@pytest.fixture
def sample_source_with_sections():
    return Source(
        id="test_source_456",
        name="Multi-Section Source",
        url="https://example.com/main",
        enabled=True,
        type="guide",
        category="education",
        section_urls=[
            "https://example.com/section1",
            "https://example.com/section2",
            "https://example.com/section3"
        ],
        total_chunks=15,
        last_sync=datetime.now(UTC)
    )


@pytest.fixture
def multiple_sources() -> List[Source]:
    return [
        Source(
            id=f"source_{i}",
            name=f"Source {i}",
            url=f"https://example{i}.com",
            enabled=i % 2 == 0,
            type="article",
            category="finance"
        )
        for i in range(1, 6)
    ]


@pytest.fixture
def sample_document():
    return Document(
        page_content="This is test content for document processing.",
        metadata={"source": "https://example.com/page1", "title": "Test Page"}
    )


@pytest.fixture
def sample_documents():
    return [
        Document(
            page_content=f"Content {i} with some substantial text to process. This is a longer piece of content that should not trigger JavaScript detection. It contains enough text to be considered valid content without needing JavaScript rendering. The content includes multiple sentences and provides meaningful information for testing purposes. This ensures that the document processing pipeline works correctly with realistic content lengths.",
            metadata={"source": f"https://example.com/page{i}"}
        )
        for i in range(3)
    ]


@pytest.fixture
def sample_embedding():
    return [0.1] * 1536


@pytest.fixture
def sample_embeddings():
    return [[0.1 * i + j * 0.01 for i in range(1536)] for j in range(5)]



@pytest.fixture
def temp_log_file(tmp_path):
    log_file = tmp_path / "test_crawl.log"
    log_file.touch()
    return str(log_file)


@pytest.fixture
def mock_bedrock_embeddings(mocker):
    mock = mocker.patch('app.knowledge.document_service.BedrockEmbeddings')
    mock_instance = MagicMock()
    mock_instance.embed_documents.return_value = [[0.1] * 1536 for _ in range(10)]
    mock_instance.embed_query.return_value = [0.1] * 1536
    mock.return_value = mock_instance
    return mock_instance


@pytest.fixture
def mock_s3_vectors_client(mocker):
    mock_client = MagicMock()
    mock_client.put_vectors.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
    mock_client.delete_vectors.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
    mock_client.get_paginator.return_value.paginate.return_value = []
    mock_client.query_vectors.return_value = {"vectors": []}
    mock_boto3 = mocker.patch('boto3.client')
    mock_boto3.return_value = mock_client
    return mock_client


@pytest.fixture
def mock_text_splitter(mocker):
    mock = mocker.patch('app.knowledge.document_service.RecursiveCharacterTextSplitter')
    mock_instance = MagicMock()

    def split_documents(docs):
        chunks = []
        for doc in docs:
            for i in range(2):
                chunk = Document(
                    page_content=doc.page_content[:len(doc.page_content)//2] if i == 0 else doc.page_content[len(doc.page_content)//2:],
                    metadata=doc.metadata.copy()
                )
                chunks.append(chunk)
        return chunks

    mock_instance.split_documents.side_effect = split_documents
    mock.return_value = mock_instance
    return mock_instance


@pytest.fixture
def mock_crawler_service(mocker):
    mock = mocker.patch('app.knowledge.service.CrawlerService')
    mock_instance = AsyncMock()

    async def crawl_source(source):
        return {
            "documents": [],
            "documents_loaded": 0,
            "source_url": source.url,
            "message": "Mock crawl",
            "crawl_type": "mock"
        }

    mock_instance.crawl_source.side_effect = crawl_source
    mock.return_value = mock_instance
    return mock_instance


@pytest.fixture
def mock_config(mocker):
    mock = mocker.patch('app.knowledge.service.config')
    mock.MAX_CHUNKS_PER_SOURCE = 100
    mock.CHUNK_SIZE = 1000
    mock.CHUNK_OVERLAP = 200
    mock.BEDROCK_EMBED_MODEL_ID = "amazon.titan-embed-text-v1"
    mock.AWS_REGION = "us-east-1"
    mock.S3V_BUCKET = "test-bucket"
    mock.S3V_INDEX_KB = "test-index"
    mock.TOP_K_SEARCH = 5
    mock.CRAWL_TYPE = "recursive"
    mock.CRAWL_TIMEOUT = 30
    return mock


VALID_URLS = [
    "https://example.com",
    "http://example.com/page",
    "https://example.com/path/to/page.html",
    "https://example.com/document.pdf"
]

INVALID_URLS = [
    "not-a-url",
    "ftp://example.com",
    "",
    None
]

EXCLUDED_URLS = [
    "https://example.com/style.css",
    "https://example.com/script.js",
    "https://example.com/image.png",
    "https://example.com/wp-admin/",
    "https://example.com/api/endpoint"
]

VALID_CONTENT_URLS = [
    "https://example.com/about",
    "https://example.com/blog/post",
    "https://example.com/products/item-1",
    "https://example.com/documentation.pdf"
]


__all__ = [
    'VALID_URLS',
    'INVALID_URLS',
    'EXCLUDED_URLS',
    'VALID_CONTENT_URLS'
]
