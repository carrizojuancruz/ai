from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document

from app.knowledge.document_service import DocumentService


@pytest.mark.unit
class TestDocumentService:

    @pytest.fixture
    def mock_bedrock_embeddings(self, mocker):
        mock = mocker.patch('app.knowledge.document_service.BedrockEmbeddings')
        mock_instance = MagicMock()

        def embed_documents(texts):
            return [[0.1] * 1536 for _ in texts]

        mock_instance.embed_documents.side_effect = embed_documents
        mock_instance.embed_query.return_value = [0.1] * 1536
        mock.return_value = mock_instance
        return mock_instance

    @pytest.fixture
    def mock_text_splitter(self, mocker):
        mock = mocker.patch('app.knowledge.document_service.RecursiveCharacterTextSplitter')
        mock_instance = MagicMock()

        def split_documents(docs):
            chunks = []
            for doc in docs:
                mid = len(doc.page_content) // 2
                for i in range(2):
                    chunk = Document(
                        page_content=doc.page_content[:mid] if i == 0 else doc.page_content[mid:],
                        metadata=doc.metadata.copy()
                    )
                    chunks.append(chunk)
            return chunks

        mock_instance.split_documents.side_effect = split_documents
        mock.return_value = mock_instance
        return mock_instance

    @pytest.fixture
    def document_service(self, mock_bedrock_embeddings):
        return DocumentService()

    def test_split_documents_basic(self, document_service, mock_text_splitter, sample_source, sample_documents):
        chunks = document_service.split_documents(sample_documents, sample_source)

        assert len(chunks) > 0
        assert all(isinstance(chunk, Document) for chunk in chunks)
        assert all('source_id' in chunk.metadata for chunk in chunks)
        assert all(chunk.metadata['source_id'] == sample_source.id for chunk in chunks)

    def test_split_documents_metadata_enrichment(self, document_service, mock_text_splitter, sample_source):
        docs = [
            Document(
                page_content="Test content " * 100,
                metadata={"source": "https://example.com/page1"}
            )
        ]

        chunks = document_service.split_documents(docs, sample_source)

        for chunk in chunks:
            assert chunk.metadata['source_id'] == sample_source.id
            assert chunk.metadata['source_url'] == sample_source.url
            assert chunk.metadata['name'] == sample_source.name
            assert 'content_hash' in chunk.metadata
            assert 'chunk_index' in chunk.metadata

    def test_split_documents_with_section_url(self, document_service, mock_text_splitter, sample_source):
        docs = [
            Document(
                page_content="Test content",
                metadata={"source": "https://example.com/section1"}
            )
        ]

        chunks = document_service.split_documents(docs, sample_source)

        assert all(chunk.metadata['section_url'] == "https://example.com/section1" for chunk in chunks)

    def test_content_hash_generation(self, document_service, mock_text_splitter, sample_source):
        docs1 = [Document(page_content="Test content", metadata={})]
        docs2 = [Document(page_content="Test content", metadata={})]

        chunks1 = document_service.split_documents(docs1, sample_source)
        chunks2 = document_service.split_documents(docs2, sample_source)

        hash1 = chunks1[0].metadata['content_hash']
        hash2 = chunks2[0].metadata['content_hash']

        assert hash1 == hash2
        assert len(hash1) == 64

    def test_empty_document_list(self, document_service, sample_source):
        chunks = document_service.split_documents([], sample_source)
        assert chunks == []

    def test_generate_embeddings_single_text(self, document_service, mock_bedrock_embeddings):
        embeddings = document_service.generate_embeddings(["test text"])

        assert len(embeddings) == 1
        assert len(embeddings[0]) == 1536
        mock_bedrock_embeddings.embed_documents.assert_called_once()

    def test_generate_embeddings_batch(self, document_service, mock_bedrock_embeddings):
        texts = [f"Text {i}" for i in range(10)]
        embeddings = document_service.generate_embeddings(texts)

        assert len(embeddings) == 10
        assert all(len(emb) == 1536 for emb in embeddings)

    def test_generate_query_embedding(self, document_service, mock_bedrock_embeddings):
        embedding = document_service.generate_query_embedding("test query")

        assert len(embedding) == 1536
        mock_bedrock_embeddings.embed_query.assert_called_once_with("test query")

    def test_embedding_error_handling(self, document_service, mock_bedrock_embeddings):
        mock_bedrock_embeddings.embed_documents.side_effect = Exception("Bedrock error")

        with pytest.raises(Exception, match="Bedrock error"):
            document_service.generate_embeddings(["test"])


@pytest.mark.unit
class TestDocumentServiceSubcategory:

    @pytest.fixture
    def mock_bedrock_embeddings(self, mocker):
        mock = mocker.patch('app.knowledge.document_service.BedrockEmbeddings')
        mock_instance = MagicMock()
        mock_instance.embed_documents.return_value = [[0.1] * 1536 for _ in range(10)]
        mock.return_value = mock_instance
        return mock_instance

    @pytest.fixture
    def mock_text_splitter(self, mocker):
        mock = mocker.patch('app.knowledge.document_service.RecursiveCharacterTextSplitter')
        mock_instance = MagicMock()

        def split_documents(docs):
            return [
                Document(
                    page_content=doc.page_content[:len(doc.page_content)//2] if i == 0 else doc.page_content[len(doc.page_content)//2:],
                    metadata=doc.metadata.copy()
                )
                for doc in docs for i in range(2)
            ]

        mock_instance.split_documents.side_effect = split_documents
        mock.return_value = mock_instance
        return mock_instance

    @pytest.fixture
    def document_service(self, mock_bedrock_embeddings):
        return DocumentService()

    @pytest.fixture
    def internal_source(self):
        from app.knowledge.models import Source
        return Source(
            id="int123",
            name="Internal",
            url="Profile/file.md",
            enabled=True,
            type="markdown"
        )

    def test_s3_subcategory_assignment(self, document_service, mock_text_splitter, internal_source):
        docs = [
            Document(
                page_content="Test " * 50,
                metadata={"s3_key": "Profile/file.md"}
            )
        ]

        chunks = document_service.split_documents(docs, internal_source, content_source="internal")

        assert all(chunk.metadata.get('subcategory') == 'profile' for chunk in chunks)

    def test_url_fallback(self, document_service, mock_text_splitter):
        from app.knowledge.models import Source

        source = Source(id="url123", name="URL", url="https://example.com", enabled=True, type="article")

        docs = [
            Document(
                page_content="Test " * 50,
                metadata={"source": "https://example.com/12634022-see-how-you-re-doing-reports-made-simple", "s3_key": ""}
            )
        ]

        chunks = document_service.split_documents(docs, source, content_source="internal")

        assert all(chunk.metadata.get('subcategory') == 'reports' for chunk in chunks)

    def test_no_subcategory(self, document_service, mock_text_splitter):
        from app.knowledge.models import Source

        source = Source(id="other", name="Other", url="https://example.com", enabled=True)

        docs = [Document(page_content="Test " * 50, metadata={"s3_key": "Other/file.md"})]

        chunks = document_service.split_documents(docs, source, content_source="internal")

        assert all(chunk.metadata.get('subcategory', '') == '' for chunk in chunks)

    def test_external_no_subcategory(self, document_service, mock_text_splitter, sample_source):
        docs = [Document(page_content="External " * 50, metadata={})]

        chunks = document_service.split_documents(docs, sample_source, content_source="external")

        assert all('subcategory' not in chunk.metadata or chunk.metadata.get('subcategory') == ''
                   for chunk in chunks)

    def test_case_insensitive(self, document_service, mock_text_splitter, internal_source):
        docs = [Document(page_content="Test " * 50, metadata={"s3_key": "profile/file.md"})]

        chunks = document_service.split_documents(docs, internal_source, content_source="internal")

        assert all(chunk.metadata.get('subcategory') == 'profile' for chunk in chunks)

    def test_s3_priority(self, document_service, mock_text_splitter):
        from app.knowledge.models import Source

        source = Source(id="mix", name="Mixed", url="https://example.com", enabled=True)

        docs = [
            Document(
                page_content="Test " * 50,
                metadata={
                    "s3_key": "Profile/file.md",
                    "section_url": "https://example.com/12634022-see-how-you-re-doing-reports-made-simple"
                }
            )
        ]

        chunks = document_service.split_documents(docs, source, content_source="internal")

        assert all(chunk.metadata.get('subcategory') == 'profile' for chunk in chunks)
