from unittest.mock import AsyncMock, MagicMock

import pytest

from app.knowledge.models import Source
from app.knowledge.service import KnowledgeService


@pytest.mark.unit
class TestKnowledgeService:

    @pytest.fixture
    def mock_vector_store(self, mocker):
        mock = mocker.patch('app.knowledge.service.S3VectorStoreService')
        mock_instance = MagicMock()
        mock_instance.delete_all_vectors.return_value = {
            "success": True,
            "vectors_deleted": 10,
            "message": "Successfully deleted vectors"
        }
        mock_instance.delete_documents_by_source_id.return_value = {"success": True}
        mock_instance.add_documents.return_value = None
        mock_instance.similarity_search.return_value = []
        mock_instance.get_source_chunk_hashes.return_value = set()
        mock.return_value = mock_instance
        return mock_instance

    @pytest.fixture
    def mock_source_repository(self, mocker):
        mock = mocker.patch('app.knowledge.service.SourceRepository')
        mock_instance = MagicMock()
        mock_instance.delete_all.return_value = None
        mock_instance.delete_by_url.return_value = True
        mock_instance.find_by_url.return_value = None
        mock_instance.load_all.return_value = []
        mock_instance.save_all.return_value = None
        mock.return_value = mock_instance
        return mock_instance

    @pytest.fixture
    def mock_document_service(self, mocker):
        mock = mocker.patch('app.knowledge.service.DocumentService')
        mock_instance = MagicMock()
        mock_instance.split_documents.return_value = []
        mock_instance.generate_embeddings.return_value = []
        mock_instance.generate_query_embedding.return_value = [0.1] * 1536
        mock.return_value = mock_instance
        return mock_instance

    @pytest.fixture
    def mock_crawler_service(self, mocker):
        mock = mocker.patch('app.knowledge.service.CrawlerService')
        mock_instance = AsyncMock()
        mock_instance.crawl_source.return_value = {
            "documents": [],
            "documents_loaded": 0,
            "source_url": "https://example.com",
            "message": "Mock crawl"
        }
        mock.return_value = mock_instance
        return mock_instance

    @pytest.fixture
    def knowledge_service(
        self,
        mock_vector_store,
        mock_source_repository,
        mock_document_service,
        mock_crawler_service
    ):
        return KnowledgeService()

    @pytest.mark.parametrize("success,vectors_deleted,expected_success", [
        (True, 10, True),
        (False, 0, False),
    ])
    def test_delete_all_vectors_scenarios(
        self,
        knowledge_service,
        mock_vector_store,
        mock_source_repository,
        success,
        vectors_deleted,
        expected_success
    ):
        mock_vector_store.delete_all_vectors.return_value = {
            "success": success,
            "vectors_deleted": vectors_deleted,
            "vectors_failed": 5 if not success else 0,
            "message": "Successfully deleted vectors" if success else "Failed to delete vectors"
        }

        result = knowledge_service.delete_all_vectors()

        mock_vector_store.delete_all_vectors.assert_called_once()
        if success:
            mock_source_repository.delete_all.assert_called_once()
        assert result["success"] is expected_success

    @pytest.mark.parametrize("source_found,vector_delete_success,expect_repo_delete,expected_success", [
        (True, True, True, True),   # Success path
        (True, False, False, False),  # Vector deletion fails
        (False, None, False, False),  # Source not found
    ])
    def test_delete_source_scenarios(
        self,
        knowledge_service,
        mock_vector_store,
        mock_source_repository,
        sample_source,
        source_found,
        vector_delete_success,
        expect_repo_delete,
        expected_success
    ):
        url = sample_source.url if source_found else "https://notfound.example.com"
        mock_source_repository.find_by_url.return_value = sample_source if source_found else None

        if source_found and vector_delete_success is not None:
            mock_vector_store.delete_documents_by_source_id.return_value = {
                "success": vector_delete_success,
                "message": "Success" if vector_delete_success else "Failed to delete documents"
            }

        result = knowledge_service.delete_source(url)

        if source_found:
            mock_vector_store.delete_documents_by_source_id.assert_called_once_with(sample_source.id)
        if expect_repo_delete:
            mock_source_repository.delete_by_url.assert_called_once_with(url)
        else:
            mock_source_repository.delete_by_url.assert_not_called()

        assert result["success"] is expected_success

    @pytest.mark.asyncio
    async def test_upsert_source_new_source(
        self,
        knowledge_service,
        mock_crawler_service,
        mock_document_service,
        mock_vector_store,
        mock_source_repository,
        sample_source,
        sample_documents
    ):
        from langchain_core.documents import Document

        chunks = [
            Document(
                page_content=f"Chunk {i}",
                metadata={"source_id": sample_source.id, "content_hash": f"hash{i}"}
            )
            for i in range(20)
        ]

        mock_crawler_service.crawl_source.return_value = {
            "documents": sample_documents,
            "documents_loaded": 5
        }
        mock_document_service.split_documents.return_value = chunks
        mock_document_service.generate_embeddings.return_value = [[0.1] * 1536] * 20

        result = await knowledge_service.upsert_source(sample_source)

        assert result["success"] is True
        assert result["is_new_source"] is True
        assert result["documents_added"] == 20

    @pytest.mark.asyncio
    async def test_upsert_source_no_documents_from_crawler(
        self,
        knowledge_service,
        mock_crawler_service,
        sample_source
    ):
        mock_crawler_service.crawl_source.return_value = {
            "documents": [],
            "documents_loaded": 0
        }

        result = await knowledge_service.upsert_source(sample_source)

        assert result["success"] is True
        assert result["documents_added"] == 0

    def test_get_sources(self, knowledge_service, mock_source_repository):

        sources = [
            Source(id="s1", name="Source 1", url="https://example1.com"),
            Source(id="s2", name="Source 2", url="https://example2.com")
        ]
        mock_source_repository.load_all.return_value = sources

        result = knowledge_service.get_sources()

        assert len(result) == 2
        assert all(isinstance(s, Source) for s in result)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("has_results,has_exception,expected_count", [
        (True, False, 1),   # Success with results
        (False, False, 0),  # Empty results
        (False, True, 0),   # Exception handled
    ])
    async def test_search_scenarios(
        self,
        knowledge_service,
        mock_vector_store,
        mock_document_service,
        has_results,
        has_exception,
        expected_count
    ):
        if has_exception:
            mock_document_service.generate_query_embedding.side_effect = Exception("Bedrock error")
        elif has_results:
            mock_vector_store.similarity_search.return_value = [
                {
                    "content": "Test content",
                    "metadata": {
                        "section_url": "https://example.com/section",
                        "source_url": "https://example.com",
                        "source_id": "s1",
                        "name": "Source 1",
                        "type": "article",
                        "category": "finance",
                        "description": "desc"
                    },
                    "score": 0.9
                }
            ]
        else:
            mock_vector_store.similarity_search.return_value = []

        results = await knowledge_service.search("test query")

        assert len(results) == expected_count
        if has_results:
            item = results[0]
            assert item["content"] == "Test content"
            assert item["source_id"] == "s1"

    @pytest.mark.parametrize("old_hashes,new_hashes,expected_reindex", [
        ({"hash1", "hash2"}, {"hash1", "hash3"}, True),   # Different hashes
        ({"hash1", "hash2"}, {"hash1", "hash2"}, False),  # Same hashes
        (set(), {"hash1"}, True),                         # Empty old hashes
    ])
    def test_needs_reindex_scenarios(
        self,
        knowledge_service,
        mock_vector_store,
        old_hashes,
        new_hashes,
        expected_reindex
    ):
        mock_vector_store.get_source_chunk_hashes.return_value = old_hashes

        result = knowledge_service._needs_reindex("test123", new_hashes)

        assert result is expected_reindex
        mock_vector_store.get_source_chunk_hashes.assert_called_once_with("test123")

    @pytest.mark.asyncio
    async def test_upsert_source_no_changes_skips_reindex(
        self,
        knowledge_service,
        mock_source_repository,
        mock_document_service,
        mock_vector_store,
        sample_source,
        mocker
    ):
        from langchain_core.documents import Document

        # Existing source present
        mock_source_repository.find_by_url.return_value = sample_source

        # Prepare chunks with known hashes
        chunks = [
            Document(page_content="a", metadata={"content_hash": "h1"}),
            Document(page_content="b", metadata={"content_hash": "h2"}),
        ]
        mock_document_service.split_documents.return_value = chunks
        mock_vector_store.get_source_chunk_hashes.return_value = {"h1", "h2"}

        # Ensure crawler returns some documents for the existing service instance
        knowledge_service.crawler_service.crawl_source = AsyncMock(
            return_value={"documents": [Document(page_content="doc", metadata={})], "documents_loaded": 1}
        )

        result = await knowledge_service.upsert_source(sample_source)

        assert result["success"] is True
        assert result["message"] == "No changes detected"
        assert result["is_new_source"] is False
        assert result["documents_added"] == 0
        # Ensure we didn't attempt to delete/add when no changes
        knowledge_service.vector_store_service.add_documents.assert_not_called()

    @pytest.mark.asyncio
    async def test_upsert_source_applies_chunk_limit(
        self,
        knowledge_service,
        mock_document_service,
        mock_vector_store,
        sample_source,
        mocker
    ):
        from langchain_core.documents import Document

        # Set a small max chunks limit
        cfg = mocker.patch('app.knowledge.service.config')
        cfg.MAX_CHUNKS_PER_SOURCE = 5

        # Create 10 chunks from split
        chunks = [Document(page_content=f"c{i}", metadata={"content_hash": f"h{i}"}) for i in range(10)]
        mock_document_service.split_documents.return_value = chunks
        mock_document_service.generate_embeddings.return_value = [[0.1] * 1536] * 5

        # Ensure crawler returns documents so we exercise chunk limiting
        knowledge_service.crawler_service.crawl_source = AsyncMock(
            return_value={"documents": [Document(page_content="doc", metadata={})], "documents_loaded": 1}
        )
        # No existing source so it is an insert path
        result = await knowledge_service.upsert_source(sample_source)

        assert result["success"] is True
        # Ensure add_documents called with limited number of chunks
        args, kwargs = knowledge_service.vector_store_service.add_documents.call_args
        limited_chunks = args[0]
        assert len(limited_chunks) == 5

    @pytest.mark.parametrize("source_exists,has_vectors,vector_error,expected_chunks", [
        (False, False, False, 0),   # Source not found
        (True, True, False, 2),     # Success with vectors
        (True, False, True, 0),     # Vector iteration error
    ])
    def test_get_source_details_scenarios(
        self,
        knowledge_service,
        mock_source_repository,
        mock_vector_store,
        source_exists,
        has_vectors,
        vector_error,
        expected_chunks
    ):
        source = Source(
            id="test123",
            name="Test Source",
            url="https://example.com",
            type="web",
            category="test",
            description="Test description",
            total_max_pages=10,
            recursion_depth=2,
            last_sync="2024-01-01",
            section_urls=["https://example.com/section1"] if has_vectors else []
        )

        mock_source_repository.load_all.return_value = [source] if source_exists else []

        if source_exists:
            if vector_error:
                mock_vector_store._iterate_vectors_by_source_id.side_effect = Exception("Vector store error")
            elif has_vectors:
                vectors = [
                    {"metadata": {"url": "https://example.com/section1", "content": "Test content 1"}},
                    {"metadata": {"url": "https://example.com/section2", "content": "Test content 2"}}
                ]
                mock_vector_store._iterate_vectors_by_source_id.return_value = iter(vectors)

        result = knowledge_service.get_source_details("test123" if source_exists else "nonexistent")

        if not source_exists:
            assert result == {"error": "Source with id nonexistent not found"}
        else:
            assert "source" in result
            assert result["source"]["id"] == "test123"
            assert result["total_chunks"] == expected_chunks
            assert len(result["chunks"]) == expected_chunks
            if has_vectors and not vector_error:
                assert result["chunks"][0]["section_url"] == "https://example.com/section1"
