import pytest
from unittest.mock import patch

from app.knowledge.service import KnowledgeService


@pytest.fixture
def knowledge_service(mock_sources_file):
    return KnowledgeService()


class TestKnowledgeService:

    @pytest.mark.asyncio
    async def test_upsert_source_new_source_success(self, knowledge_service, sample_source, sample_documents):
        with patch.object(knowledge_service.crawler_service, 'crawl_source') as mock_crawl:
            mock_crawl.return_value = {
                "documents": sample_documents,
                "message": "Crawl successful"
            }

            result = await knowledge_service.upsert_source(sample_source)

            assert result["success"] is True
            assert result["is_new_source"] is True
            assert result["documents_added"] > 0
            assert result["documents_processed"] == len(sample_documents)

    @pytest.mark.asyncio
    async def test_upsert_source_no_changes_detected(self, knowledge_service, sample_source, sample_documents):
        knowledge_service.source_repository.upsert(sample_source)

        with patch.object(knowledge_service.crawler_service, 'crawl_source') as mock_crawl, \
             patch.object(knowledge_service, '_needs_reindex', return_value=False):

            mock_crawl.return_value = {"documents": sample_documents, "message": "Crawl successful"}
            result = await knowledge_service.upsert_source(sample_source)

            assert result["success"] is True
            assert result["is_new_source"] is False
            assert result["documents_added"] == 0

    @pytest.mark.asyncio
    async def test_upsert_source_crawl_failure(self, knowledge_service, sample_source):
        with patch.object(knowledge_service.crawler_service, 'crawl_source') as mock_crawl:
            mock_crawl.return_value = {
                "documents": [],
                "message": "No documents found",
                "error": "Site unreachable"
            }

            result = await knowledge_service.upsert_source(sample_source)

            assert result["success"] is True
            assert result["documents_added"] == 0
            assert result["crawl_error"] == "Site unreachable"

    @pytest.mark.asyncio
    async def test_search_knowledge_base(self, knowledge_service):
        query = "investment strategies"

        results = await knowledge_service.search(query)

        assert isinstance(results, list)
        assert len(results) == 1

        result = results[0]
        assert "content" in result
        assert "source_id" in result
        assert result["content"] == "Sample financial content"
        assert result["source_id"] == "test-source-1"

    def test_get_sources(self, knowledge_service):
        sources = knowledge_service.get_sources()
        assert isinstance(sources, list)

    def test_delete_all_vectors(self, knowledge_service):
        result = knowledge_service.delete_all_vectors()

        assert "vectors_deleted" in result
        assert result["success"] is True

    def test_delete_source(self, knowledge_service, sample_source):
        knowledge_service.source_repository.upsert(sample_source)

        result = knowledge_service.delete_source(sample_source)

        assert result["success"] is True
