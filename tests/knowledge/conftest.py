import pytest
from unittest.mock import Mock, patch

from app.knowledge.models import Source


@pytest.fixture
def sample_source():
    return Source(
        id="test-source-1",
        name="Test Documentation",
        url="https://example.com/docs",
        type="documentation",
        category="finance",
        enabled=True
    )


@pytest.fixture
def sample_documents():
    from langchain_core.documents import Document

    return [
        Document(
            page_content="Investment strategies are crucial for building wealth.",
            metadata={"source": "https://example.com/docs/investments", "title": "Investment Guide"}
        ),
        Document(
            page_content="Retirement planning requires long-term thinking.",
            metadata={"source": "https://example.com/docs/retirement", "title": "Retirement Planning"}
        )
    ]


@pytest.fixture
def mock_sources_file(tmp_path):
    sources_file = tmp_path / "sources.json"
    sources_file.write_text('[]')

    with patch('app.core.config.config.SOURCES_FILE_PATH', str(sources_file)):
        yield sources_file


@pytest.fixture(autouse=True)
def mock_external_services():
    with patch('boto3.client') as mock_boto, \
         patch('app.knowledge.document_service.BedrockEmbeddings') as mock_bedrock, \
         patch('aiohttp.ClientSession'), \
         patch('requests.get'), \
         patch('app.core.config.config.MAX_CHUNKS_PER_SOURCE', 1000), \
         patch('app.core.config.config.S3V_BUCKET', 'test-bucket'), \
         patch('app.core.config.config.S3V_INDEX_KB', 'test-index'):

        s3_client = Mock()
        s3_client.put_vectors.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200}}
        s3_client.query_vectors.return_value = {
            'vectors': [{
                'key': 'test_doc_1',
                'metadata': {'content': 'Sample financial content', 'source_id': 'test-source-1'},
                'score': 0.95
            }]
        }
        s3_client.delete_vectors.return_value = {'deleted_count': 5}
        s3_client.list_vectors.return_value = {'vectors': []}
        mock_boto.return_value = s3_client

        embeddings_mock = Mock()
        embeddings_mock.embed_documents.return_value = [[0.1] * 384]
        embeddings_mock.embed_query.return_value = [0.1] * 384
        mock_bedrock.return_value = embeddings_mock

        yield
