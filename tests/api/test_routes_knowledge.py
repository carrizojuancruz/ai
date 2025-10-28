"""Tests for knowledge routes."""

from unittest.mock import patch

from fastapi.testclient import TestClient


class TestKnowledgeRoutes:
    def test_search_knowledge_base_success(self, client: TestClient, mock_knowledge_service):
        """Test successful knowledge base search validates API contract."""
        # Arrange
        request_data = {"query": "test query"}
        mock_results = [
            {
                "content": "test content",
                "section_url": "https://example.com#section",
                "source_url": "https://example.com",
                "source_id": "source_1",
                "name": "Test Source",
                "type": "web",
                "category": "documentation",
                "description": "Test description"
            }
        ]
        mock_knowledge_service.search.return_value = mock_results

        with patch("app.api.routes_knowledge.KnowledgeService", return_value=mock_knowledge_service):
            # Act
            response = client.post("/knowledge/search", json=request_data)

            # Assert
            assert response.status_code == 200
            data = response.json()
            # Contract: top-level shape
            assert "query" in data and data["query"] == request_data["query"]
            assert "total_results" in data and isinstance(data["total_results"], int)
            assert "results" in data and isinstance(data["results"], list)
            assert data["total_results"] == len(data["results"]) == 1
            # Contract: result item shape
            item = data["results"][0]
            for key in ("content", "section_url", "source_url", "source_id", "name", "type", "category", "description"):
                assert key in item and isinstance(item[key], str)

            mock_knowledge_service.search.assert_called_once_with("test query", filter=None)

    def test_search_knowledge_base_error(self, client: TestClient, mock_knowledge_service):
        """Test knowledge base search with service error."""
        # Arrange
        request_data = {"query": "test query"}
        mock_knowledge_service.search.side_effect = Exception("Search failed")

        with patch("app.api.routes_knowledge.KnowledgeService", return_value=mock_knowledge_service):
            # Act
            response = client.post("/knowledge/search", json=request_data)

            # Assert
            assert response.status_code == 500
            data = response.json()
            assert "Search failed" in data["detail"]

    def test_get_sources_success(self, client: TestClient, mock_knowledge_service):
        """Test successful retrieval of knowledge sources validates API contract."""
        # Arrange
        from app.knowledge.models import Source
        mock_source = Source(
            id="source_1",
            name="Test Source",
            url="https://example.com",
            type="web",
            category="documentation",
            description="Test description",
            include_path_patterns="",
            exclude_path_patterns="",
            total_max_pages=100,
            recursion_depth=2,
            last_sync="2023-01-01T00:00:00Z",
            section_urls=["https://example.com#section1"]
        )
        mock_knowledge_service.get_sources.return_value = [mock_source]

        with patch("app.api.routes_knowledge.KnowledgeService", return_value=mock_knowledge_service):
            # Act
            response = client.get("/knowledge/sources")

            # Assert
            assert response.status_code == 200
            data = response.json()
            # Contract: top-level shape
            assert "total_sources" in data and isinstance(data["total_sources"], int)
            assert "sources" in data and isinstance(data["sources"], list)
            assert data["total_sources"] == len(data["sources"]) == 1
            # Contract: source item shape
            src = data["sources"][0]
            for key in ("id", "name", "url", "type", "category"):
                assert key in src and isinstance(src[key], str)
            # Optional fields if present
            if "description" in src:
                assert isinstance(src["description"], str) or src["description"] is None

            mock_knowledge_service.get_sources.assert_called_once()

    def test_get_sources_error(self, client: TestClient, mock_knowledge_service):
        """Test sources retrieval with service error."""
        # Arrange
        mock_knowledge_service.get_sources.side_effect = Exception("Database error")

        with patch("app.api.routes_knowledge.KnowledgeService", return_value=mock_knowledge_service):
            # Act
            response = client.get("/knowledge/sources")

            # Assert
            assert response.status_code == 500
            data = response.json()
            assert "Failed to retrieve sources" in data["detail"]

    def test_get_source_details_success(self, client: TestClient, mock_knowledge_service):
        """Test successful retrieval of source details validates API contract."""
        # Arrange
        source_id = "source_1"
        mock_details = {
            "source": {
                "id": "source_1",
                "name": "Test Source",
                "url": "https://example.com",
                "type": "web",
                "category": "documentation",
                "description": "Test description",
                "total_max_pages": 100,
                "recursion_depth": 2,
                "last_sync": "2023-01-01T00:00:00Z",
                "section_urls": ["https://example.com#section1"]
            },
            "total_chunks": 5,
            "chunks": [
                {"section_url": "https://example.com#section1", "content": "chunk content 1"},
                {"section_url": "https://example.com#section2", "content": "chunk content 2"},
                {"section_url": "https://example.com#section3", "content": "chunk content 3"},
                {"section_url": "https://example.com#section4", "content": "chunk content 4"},
                {"section_url": "https://example.com#section5", "content": "chunk content 5"}
            ]
        }
        mock_knowledge_service.get_source_details.return_value = mock_details

        with patch("app.api.routes_knowledge.KnowledgeService", return_value=mock_knowledge_service):
            # Act
            response = client.get(f"/knowledge/sources/{source_id}")

            # Assert
            assert response.status_code == 200
            data = response.json()
            # Contract: top-level keys
            assert "source" in data and isinstance(data["source"], dict)
            assert "total_chunks" in data and isinstance(data["total_chunks"], int)
            assert "chunks" in data and isinstance(data["chunks"], list)
            assert data["total_chunks"] == 5
            assert len(data["chunks"]) == 5
            # Contract: source shape
            assert data["source"]["id"] == source_id
            for key in ("name", "url", "type", "category"):
                assert key in data["source"] and isinstance(data["source"][key], str)
            # Contract: chunk shape
            if data["chunks"]:
                chunk0 = data["chunks"][0]
                assert "section_url" in chunk0 and isinstance(chunk0["section_url"], str)
                assert "content" in chunk0 and isinstance(chunk0["content"], str)

            mock_knowledge_service.get_source_details.assert_called_once_with(source_id)

    def test_get_source_details_not_found(self, client: TestClient, mock_knowledge_service):
        """Test source details retrieval for non-existent source."""
        # Arrange
        source_id = "non_existent"
        mock_details = {"error": f"Source with id {source_id} not found"}
        mock_knowledge_service.get_source_details.return_value = mock_details

        with patch("app.api.routes_knowledge.KnowledgeService", return_value=mock_knowledge_service):
            # Act
            response = client.get(f"/knowledge/sources/{source_id}")

            # Assert
            assert response.status_code == 404
            data = response.json()
            assert f"Source with id {source_id} not found" in data["detail"]

    def test_get_source_details_error(self, client: TestClient, mock_knowledge_service):
        """Test source details retrieval with service error."""
        # Arrange
        source_id = "source_1"
        mock_knowledge_service.get_source_details.side_effect = Exception("Database error")

        with patch("app.api.routes_knowledge.KnowledgeService", return_value=mock_knowledge_service):
            # Act
            response = client.get(f"/knowledge/sources/{source_id}")

            # Assert
            assert response.status_code == 500
            data = response.json()
            assert "Failed to get details" in data["detail"]

    def test_delete_all_vectors_success(self, client: TestClient, mock_knowledge_service):
        """Test successful deletion of all vectors validates API contract."""
        # Arrange
        mock_result = {
            "success": True,
            "vectors_deleted": 100,
            "message": "Successfully deleted all vectors"
        }
        mock_knowledge_service.delete_all_vectors.return_value = mock_result

        with patch("app.api.routes_knowledge.KnowledgeService", return_value=mock_knowledge_service):
            # Act
            response = client.delete("/knowledge/vectors")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert "success" in data and isinstance(data["success"], bool) and data["success"] is True
            assert "vectors_deleted" in data and isinstance(data["vectors_deleted"], int) and data["vectors_deleted"] >= 0
            assert "message" in data and isinstance(data["message"], str)

            mock_knowledge_service.delete_all_vectors.assert_called_once()

    def test_delete_all_vectors_partial_failure(self, client: TestClient, mock_knowledge_service):
        """Test deletion of all vectors with partial failure validates contract."""
        # Arrange
        mock_result = {
            "success": False,
            "vectors_deleted": 95,
            "message": "Partial deletion completed",
            "vectors_failed": 5,
            "error": "Some vectors failed to delete"
        }
        mock_knowledge_service.delete_all_vectors.return_value = mock_result

        with patch("app.api.routes_knowledge.KnowledgeService", return_value=mock_knowledge_service):
            response = client.delete("/knowledge/vectors")


            assert response.status_code == 200
            data = response.json()
            assert "success" in data and data["success"] is False
            assert "vectors_deleted" in data and isinstance(data["vectors_deleted"], int)
            assert "vectors_failed" in data and isinstance(data["vectors_failed"], int)
            assert "error" in data and isinstance(data["error"], str)

    def test_delete_all_vectors_error(self, client: TestClient, mock_knowledge_service):
        """Test deletion of all vectors with service error."""
        mock_knowledge_service.delete_all_vectors.side_effect = Exception("Vector store error")

        with patch("app.api.routes_knowledge.KnowledgeService", return_value=mock_knowledge_service):
            response = client.delete("/knowledge/vectors")

            assert response.status_code == 500
            data = response.json()
            assert "Failed to delete all vectors" in data["detail"]

    def test_sync_internal_guidance_success(self, client: TestClient):
        """Test successful internal guidance sync."""
        mock_result = {
            "success": True,
            "documents_processed": 10,
            "documents_added": 20,
            "is_new_source": True
        }

        with patch("app.api.routes_knowledge.config") as mock_config:
            mock_config.VERA_GUIDANCE_URL = "https://help.vera.com"
            mock_config.VERA_GUIDANCE_RECURSION_DEPTH = 2

            with patch("app.api.routes_knowledge.KnowledgeService") as mock_kb_class:
                mock_kb = mock_kb_class.return_value
                async def mock_upsert(source, content_source):
                    return mock_result
                mock_kb.upsert_source = mock_upsert

                response = client.post("/knowledge/sync/internal")

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["pages_crawled"] == 10
                assert data["chunks_created"] == 20
                assert "source_id" in data

    def test_sync_internal_guidance_failure(self, client: TestClient):
        """Test internal guidance sync with service failure."""
        mock_result = {
            "success": False,
            "message": "No documents found during crawl",
            "documents_processed": 0
        }

        with patch("app.api.routes_knowledge.config") as mock_config:
            mock_config.VERA_GUIDANCE_URL = "https://help.vera.com"
            mock_config.VERA_GUIDANCE_RECURSION_DEPTH = 2

            with patch("app.api.routes_knowledge.KnowledgeService") as mock_kb_class:
                mock_kb = mock_kb_class.return_value
                async def mock_upsert(source, content_source):
                    return mock_result
                mock_kb.upsert_source = mock_upsert

                response = client.post("/knowledge/sync/internal")

                assert response.status_code == 500
                assert "no documents found" in response.json()["detail"].lower()

    def test_sync_internal_guidance_missing_config(self, client: TestClient):
        """Test internal guidance sync with missing configuration."""
        with patch("app.api.routes_knowledge.config") as mock_config:
            mock_config.VERA_GUIDANCE_URL = None

            response = client.post("/knowledge/sync/internal")

            assert response.status_code == 400
            data = response.json()
            assert "not configured" in data["detail"]

    def test_sync_internal_guidance_exception(self, client: TestClient):
        """Test internal guidance sync with unexpected exception."""
        with patch("app.api.routes_knowledge.config") as mock_config:
            mock_config.VERA_GUIDANCE_URL = "https://help.vera.com"
            mock_config.VERA_GUIDANCE_RECURSION_DEPTH = 2

            with patch("app.api.routes_knowledge.KnowledgeService") as mock_kb_class:
                mock_kb = mock_kb_class.return_value
                mock_kb.upsert_source.side_effect = Exception("Unexpected error")

                response = client.post("/knowledge/sync/internal")

                assert response.status_code == 500
                data = response.json()
                assert "Internal sync failed" in data["detail"]

    def test_delete_all_s3_files_success(self, client: TestClient):
        """Test successful deletion of all S3 files."""
        mock_result = {
            "success": True,
            "total": 5,
            "succeeded": 5,
            "failed": 0,
            "total_vectors_deleted": 50,
            "details": [
                {"success": True, "s3_key": "file1.md", "vectors_deleted": 10},
                {"success": True, "s3_key": "file2.md", "vectors_deleted": 10},
                {"success": True, "s3_key": "file3.md", "vectors_deleted": 10},
                {"success": True, "s3_key": "file4.md", "vectors_deleted": 10},
                {"success": True, "s3_key": "file5.md", "vectors_deleted": 10},
            ]
        }

        with patch("app.api.routes_knowledge.S3SyncService") as mock_s3_class:
            mock_s3 = mock_s3_class.return_value
            mock_s3.delete_all_files.return_value = mock_result

            response = client.delete("/knowledge/s3/files")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["total"] == 5
            assert data["succeeded"] == 5
            assert data["failed"] == 0
            assert data["total_vectors_deleted"] == 50
            mock_s3.delete_all_files.assert_called_once()

    def test_delete_all_s3_files_with_prefix(self, client: TestClient):
        """Test deletion of S3 files."""
        mock_result = {
            "success": True,
            "total": 2,
            "succeeded": 2,
            "failed": 0,
            "total_vectors_deleted": 20,
            "details": [
                {"success": True, "s3_key": "guides/file1.md", "vectors_deleted": 10},
                {"success": True, "s3_key": "guides/file2.md", "vectors_deleted": 10},
            ]
        }

        with patch("app.api.routes_knowledge.S3SyncService") as mock_s3_class:
            mock_s3 = mock_s3_class.return_value
            mock_s3.delete_all_files.return_value = mock_result

            response = client.delete("/knowledge/s3/files")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert data["succeeded"] == 2
            mock_s3.delete_all_files.assert_called_once()

    def test_delete_all_s3_files_without_vectors(self, client: TestClient):
        """Test deletion of S3 files."""
        mock_result = {
            "success": True,
            "total": 3,
            "succeeded": 3,
            "failed": 0,
            "total_vectors_deleted": 0,
            "details": [
                {"success": True, "s3_key": "file1.md", "vectors_deleted": 0},
                {"success": True, "s3_key": "file2.md", "vectors_deleted": 0},
                {"success": True, "s3_key": "file3.md", "vectors_deleted": 0},
            ]
        }

        with patch("app.api.routes_knowledge.S3SyncService") as mock_s3_class:
            mock_s3 = mock_s3_class.return_value
            mock_s3.delete_all_files.return_value = mock_result

            response = client.delete("/knowledge/s3/files")

            assert response.status_code == 200
            data = response.json()
            assert data["total_vectors_deleted"] == 0
            mock_s3.delete_all_files.assert_called_once()

    def test_delete_all_s3_files_partial_failure(self, client: TestClient):
        """Test deletion of S3 files with partial failures."""
        mock_result = {
            "success": True,
            "total": 5,
            "succeeded": 3,
            "failed": 2,
            "total_vectors_deleted": 30,
            "details": [
                {"success": True, "s3_key": "file1.md", "vectors_deleted": 10},
                {"success": True, "s3_key": "file2.md", "vectors_deleted": 10},
                {"success": False, "s3_key": "file3.md", "error": "Access denied"},
                {"success": True, "s3_key": "file4.md", "vectors_deleted": 10},
                {"success": False, "s3_key": "file5.md", "error": "Not found"},
            ]
        }

        with patch("app.api.routes_knowledge.S3SyncService") as mock_s3_class:
            mock_s3 = mock_s3_class.return_value
            mock_s3.delete_all_files.return_value = mock_result

            response = client.delete("/knowledge/s3/files")

            assert response.status_code == 200
            data = response.json()
            assert data["succeeded"] == 3
            assert data["failed"] == 2

    def test_delete_all_s3_files_empty_bucket(self, client: TestClient):
        """Test deletion when no files exist."""
        mock_result = {
            "success": True,
            "total": 0,
            "succeeded": 0,
            "failed": 0,
            "total_vectors_deleted": 0,
            "details": []
        }

        with patch("app.api.routes_knowledge.S3SyncService") as mock_s3_class:
            mock_s3 = mock_s3_class.return_value
            mock_s3.delete_all_files.return_value = mock_result

            response = client.delete("/knowledge/s3/files")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0

    def test_delete_all_s3_files_service_error(self, client: TestClient):
        """Test deletion with service error."""
        mock_result = {
            "success": False,
            "error": "S3 connection failed",
            "total": 0,
            "succeeded": 0,
            "failed": 0
        }

        with patch("app.api.routes_knowledge.S3SyncService") as mock_s3_class:
            mock_s3 = mock_s3_class.return_value
            mock_s3.delete_all_files.return_value = mock_result

            response = client.delete("/knowledge/s3/files")

            assert response.status_code == 500
            data = response.json()
            assert "Bulk deletion failed" in data["detail"]

    def test_delete_all_s3_files_exception(self, client: TestClient):
        """Test deletion with unexpected exception."""
        with patch("app.api.routes_knowledge.S3SyncService") as mock_s3_class:
            mock_s3 = mock_s3_class.return_value
            mock_s3.delete_all_files.side_effect = Exception("Unexpected error")

            response = client.delete("/knowledge/s3/files")

            assert response.status_code == 500
            data = response.json()
            assert "Bulk deletion failed" in data["detail"]
