"""Unit and integration tests for S3SyncService."""
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from app.knowledge.s3_sync_service import S3SyncService


class TestS3SyncServiceHelpers:
    """Test helper methods of S3SyncService."""

    def test_generate_source_id_consistency(self):
        """Verify same input produces same output."""
        s3_key = "test/file.md"

        source_id_1 = S3SyncService._generate_source_id(s3_key)
        source_id_2 = S3SyncService._generate_source_id(s3_key)

        assert source_id_1 == source_id_2
        assert len(source_id_1) == 16
        assert isinstance(source_id_1, str)

    def test_generate_source_id_uniqueness(self):
        """Verify different inputs produce different outputs."""
        source_id_1 = S3SyncService._generate_source_id("file1.md")
        source_id_2 = S3SyncService._generate_source_id("file2.md")

        assert source_id_1 != source_id_2

    def test_get_file_type_markdown(self):
        """Test markdown file type detection."""
        assert S3SyncService._get_file_type("test.md") == "markdown"
        assert S3SyncService._get_file_type("test.markdown") == "markdown"

    def test_get_file_type_text(self):
        """Test text file type detection."""
        assert S3SyncService._get_file_type("test.txt") == "text"

    def test_get_file_type_json(self):
        """Test JSON file type detection."""
        assert S3SyncService._get_file_type("test.json") == "json"

    def test_get_file_type_html(self):
        """Test HTML file type detection."""
        assert S3SyncService._get_file_type("test.html") == "html"
        assert S3SyncService._get_file_type("test.htm") == "html"

    def test_get_file_type_csv(self):
        """Test CSV file type detection."""
        assert S3SyncService._get_file_type("test.csv") == "csv"

    def test_get_file_type_unknown(self):
        """Test unknown extension defaults to text."""
        assert S3SyncService._get_file_type("test.xyz") == "text"
        assert S3SyncService._get_file_type("test") == "text"

    def test_get_content_type_markdown(self):
        """Test markdown MIME type mapping."""
        content_type = S3SyncService._get_content_type("test.md")
        assert content_type in ["text/markdown", "text/plain"]

    def test_get_content_type_json(self):
        """Test JSON MIME type mapping."""
        content_type = S3SyncService._get_content_type("test.json")
        assert "json" in content_type.lower()

    def test_get_content_type_html(self):
        """Test HTML MIME type mapping."""
        content_type = S3SyncService._get_content_type("test.html")
        assert "html" in content_type.lower()

    def test_get_content_type_unknown(self):
        """Test unknown extension returns text/plain."""
        content_type = S3SyncService._get_content_type("test.unknown")
        assert content_type == "text/plain"


class TestS3SyncServiceUpload:
    """Test upload_file method."""

    @patch('app.knowledge.s3_sync_service.boto3.client')
    def test_upload_file_success(self, mock_boto_client):
        """Test successful file upload."""

        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3

        service = S3SyncService()


        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Test Content")
            temp_path = f.name

        try:

            result = service.upload_file(temp_path, "test.md")


            assert result["success"] is True
            assert result["s3_key"] == "test.md"
            assert "s3://" in result["s3_uri"]
            assert mock_s3.upload_file.called
        finally:

            Path(temp_path).unlink(missing_ok=True)

    @patch('app.knowledge.s3_sync_service.boto3.client')
    def test_upload_file_default_key(self, mock_boto_client):
        """Test upload with default s3_key from filename."""

        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3

        service = S3SyncService()


        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Test Content")
            temp_path = f.name

        try:

            result = service.upload_file(temp_path)


            assert result["success"] is True
            assert result["s3_key"] == Path(temp_path).name
        finally:

            Path(temp_path).unlink(missing_ok=True)

    @patch('app.knowledge.s3_sync_service.boto3.client')
    def test_upload_file_client_error(self, mock_boto_client):
        """Test upload with S3 client error."""
        with patch('boto3.client') as mock_boto_client_inner:
            mock_s3 = Mock()
            mock_boto_client_inner.return_value = mock_s3

            service = S3SyncService()

            def mock_upload_file(*args, **kwargs):
                raise Exception("S3 upload failed")

            service.s3_client.upload_file = mock_upload_file

            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
                f.write("# Test Content")
                temp_path = f.name

            try:

                result = service.upload_file(temp_path, "test.md")


                assert result["success"] is False
                assert "error" in result
            finally:

                Path(temp_path).unlink(missing_ok=True)
class TestS3SyncServiceList:
    """Test list_files method."""

    @patch('app.knowledge.s3_sync_service.boto3.client')
    def test_list_files_success(self, mock_boto_client):
        """Test successful file listing."""

        mock_s3 = Mock()
        mock_paginator = Mock()
        mock_s3.get_paginator.return_value = mock_paginator

        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "test1.md",
                        "Size": 1024,
                        "LastModified": datetime(2025, 1, 1)
                    },
                    {
                        "Key": "test2.md",
                        "Size": 2048,
                        "LastModified": datetime(2025, 1, 2)
                    }
                ]
            }
        ]

        mock_boto_client.return_value = mock_s3
        service = S3SyncService()


        files = service.list_files()


        assert len(files) == 2
        assert files[0]["s3_key"] == "test1.md"
        assert files[0]["size"] == 1024
        assert files[0]["size_mb"] == round(1024 / (1024 * 1024), 2)
        assert "s3_uri" in files[0]

    @patch('app.knowledge.s3_sync_service.boto3.client')
    def test_list_files_with_prefix(self, mock_boto_client):
        """Test file listing with prefix filter."""

        mock_s3 = Mock()
        mock_paginator = Mock()
        mock_s3.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"Contents": []}]

        mock_boto_client.return_value = mock_s3
        service = S3SyncService()

        service.list_files(prefix="guides/")

        mock_paginator.paginate.assert_called_once()
        call_args = mock_paginator.paginate.call_args
        assert call_args[1]["Prefix"] == "guides/"

    @patch('app.knowledge.s3_sync_service.boto3.client')
    def test_list_files_empty_bucket(self, mock_boto_client):
        """Test listing empty bucket."""
        mock_s3 = Mock()
        mock_paginator = Mock()
        mock_s3.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{}]

        mock_boto_client.return_value = mock_s3
        service = S3SyncService()

        files = service.list_files()

        assert files == []

    @patch('app.knowledge.s3_sync_service.boto3.client')
    def test_list_files_client_error(self, mock_boto_client):
        """Test listing with S3 client error."""
        mock_s3 = Mock()
        mock_paginator = Mock()
        mock_s3.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "Bucket not found"}},
            "list_objects_v2"
        )

        mock_boto_client.return_value = mock_s3
        service = S3SyncService()

        files = service.list_files()

        assert files == []


class TestS3SyncServiceDelete:
    """Test delete_file method."""

    @patch('app.knowledge.vector_store.service.S3VectorStoreService')
    @patch('app.knowledge.s3_sync_service.boto3.client')
    def test_delete_file_with_vectors(self, mock_boto_client, mock_vector_service_class):
        """Test file deletion with vector deletion."""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3

        mock_vector_service = Mock()
        mock_vector_service.delete_documents_by_source_id.return_value = {
            "success": True,
            "vectors_deleted": 5
        }
        mock_vector_service_class.return_value = mock_vector_service

        service = S3SyncService()

        result = service.delete_file("test.md", delete_vectors=True)

        assert result["success"] is True
        assert result["s3_deleted"] is True
        assert result["vectors_deleted"] == 5
        assert result["vector_deletion_success"] is True
        assert mock_s3.delete_object.called
        mock_vector_service.delete_documents_by_source_id.assert_called_once()

    @patch('app.knowledge.s3_sync_service.boto3.client')
    def test_delete_file_without_vectors(self, mock_boto_client):
        """Test file deletion without vector deletion."""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3

        service = S3SyncService()

        result = service.delete_file("test.md", delete_vectors=False)

        assert result["success"] is True
        assert result["s3_deleted"] is True
        assert result["vectors_deleted"] == 0
        assert mock_s3.delete_object.called

    @patch('app.knowledge.s3_sync_service.boto3.client')
    def test_delete_file_client_error(self, mock_boto_client):
        """Test deletion with S3 client error."""
        mock_boto_client.return_value.delete_object.side_effect = Exception(
            "NoSuchKey: Key not found"
        )

        service = S3SyncService()

        result = service.delete_file("test.md")

        assert result["success"] is False
        assert "error" in result


@pytest.mark.unit
class TestS3SyncServiceSubcategory:

    def test_source_id_generation_consistency(self):
        id1 = S3SyncService._generate_source_id("Profile/file.md")
        id2 = S3SyncService._generate_source_id("Profile/file.md")

        assert id1 == id2
