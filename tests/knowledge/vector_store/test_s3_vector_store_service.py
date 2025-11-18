from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document

from app.knowledge.vector_store.service import S3VectorStoreService


@pytest.mark.unit
class TestS3VectorStoreService:

    @pytest.fixture
    def mock_s3_client(self, mocker):
        mock_client = MagicMock()
        mock_client.put_vectors.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
        mock_client.delete_vectors.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
        mock_client.query_vectors.return_value = {"vectors": []}
        mock_client.get_paginator.return_value.paginate.return_value = []

        mock_boto3 = mocker.patch('boto3.client')
        mock_boto3.return_value = mock_client
        return mock_client

    @pytest.fixture
    def vector_store(self, mock_s3_client):
        return S3VectorStoreService()

    def test_add_documents_success(
        self,
        vector_store,
        mock_s3_client,
        sample_source,
        sample_embedding
    ):
        docs = [
            Document(
                page_content="Test content",
                metadata={
                    "source_id": sample_source.id,
                    "content_hash": "testhash",
                    "chunk_index": 0
                }
            )
        ]
        embeddings = [sample_embedding]

        vector_store.add_documents(docs, embeddings)

        mock_s3_client.put_vectors.assert_called_once()

    def test_add_documents_vector_key_format(
        self,
        vector_store,
        mock_s3_client,
        sample_source,
        sample_embedding
    ):
        docs = [
            Document(
                page_content="Content",
                metadata={
                    "source_id": "test123",
                    "content_hash": "hash456",
                    "chunk_index": 0
                }
            )
        ]

        vector_store.add_documents(docs, [sample_embedding])

        call_args = mock_s3_client.put_vectors.call_args
        vectors = call_args[1]["vectors"]
        assert vectors[0]["key"].startswith("doc_test123")

    @pytest.mark.parametrize("key_count,delete_side_effect,expected_success,expected_deleted,expected_failed,expected_msg_part", [
        (50, None, True, 50, 0, None),  # Success
        (0, None, True, 0, 0, "No vectors found"),  # Empty index
        (150, [{"ResponseMetadata": {"HTTPStatusCode": 200}}, Exception("Delete failed")], False, 100, 50, "Partially successful"),  # Partial success
        (5, Exception("Delete failed"), False, 0, 5, "Failed to delete any vectors"),  # Complete failure
    ])
    def test_delete_all_vectors_scenarios(
        self,
        vector_store,
        mock_s3_client,
        mocker,
        key_count,
        delete_side_effect,
        expected_success,
        expected_deleted,
        expected_failed,
        expected_msg_part
    ):
        mocker.patch.object(
            vector_store,
            '_get_all_vector_keys',
            return_value=[f"key_{i}" for i in range(key_count)]
        )

        if delete_side_effect:
            mock_s3_client.delete_vectors.side_effect = delete_side_effect

        result = vector_store.delete_all_vectors()

        assert result["success"] is expected_success
        if key_count > 0:
            assert result["vectors_deleted"] == expected_deleted
            if expected_failed > 0:
                assert result["vectors_failed"] == expected_failed
        if expected_msg_part:
            assert expected_msg_part in result["message"]

    def test_delete_all_vectors_get_keys_exception(
        self,
        vector_store,
        mocker
    ):
        mocker.patch.object(
            vector_store,
            '_get_all_vector_keys',
            side_effect=Exception("Get keys failed")
        )

        result = vector_store.delete_all_vectors()

        assert result["success"] is False
        assert result["vectors_found"] == 0
        assert "Deletion process failed" in result["message"]

    @pytest.mark.parametrize("key_count,expected_success,expected_msg_part", [
        (30, True, None),  # Success
        (0, True, "No vectors found"),  # Not found
    ])
    def test_delete_documents_by_source_id_scenarios(
        self,
        vector_store,
        mock_s3_client,
        mocker,
        key_count,
        expected_success,
        expected_msg_part
    ):
        mocker.patch.object(
            vector_store,
            '_get_vector_keys_by_source_id',
            return_value=[f"key_{i}" for i in range(key_count)]
        )

        result = vector_store.delete_documents_by_source_id("test123")

        assert result["success"] is expected_success
        if key_count > 0:
            mock_s3_client.delete_vectors.assert_called()
        if expected_msg_part:
            assert expected_msg_part in result["message"]

    @pytest.mark.parametrize("has_results,top_k,expected_count", [
        (True, 5, 1),   # Success with results
        (True, 10, 1),  # Respects top_k
        (False, 5, 0),  # Empty results
    ])
    def test_similarity_search_scenarios(
        self,
        vector_store,
        mock_s3_client,
        mock_vector_response,
        has_results,
        top_k,
        expected_count
    ):
        if has_results:
            mock_s3_client.query_vectors.return_value = mock_vector_response
        else:
            mock_s3_client.query_vectors.return_value = {"vectors": []}

        query_embedding = [0.1] * 1536
        results = vector_store.similarity_search(query_embedding, k=top_k)

        assert len(results) == expected_count
        call_args = mock_s3_client.query_vectors.call_args
        assert call_args[1]["topK"] == top_k

    def test_add_documents_put_vectors_exception(
        self,
        vector_store,
        mock_s3_client,
        sample_source,
        sample_embedding
    ):
        docs = [
            Document(
                page_content="Test content",
                metadata={
                    "source_id": sample_source.id,
                    "content_hash": "testhash",
                    "chunk_index": 0
                }
            )
        ]
        embeddings = [sample_embedding]

        mock_s3_client.put_vectors.side_effect = Exception("S3 error")

        with pytest.raises(Exception, match="S3 error"):
            vector_store.add_documents(docs, embeddings)

    def test_delete_all_vectors_partial_success(
        self,
        vector_store,
        mock_s3_client,
        mocker
    ):
        mocker.patch.object(
            vector_store,
            '_get_all_vector_keys',
            return_value=[f"key_{i}" for i in range(150)]
        )

        mock_s3_client.delete_vectors.side_effect = [
            {"ResponseMetadata": {"HTTPStatusCode": 200}},
            Exception("Delete failed")
        ]

        result = vector_store.delete_all_vectors()

        assert result["success"] is False
        assert result["vectors_deleted"] == 100
        assert result["vectors_failed"] == 50
        assert "Partially successful" in result["message"]

    def test_delete_all_vectors_complete_failure(
        self,
        vector_store,
        mock_s3_client,
        mocker
    ):
        mocker.patch.object(
            vector_store,
            '_get_all_vector_keys',
            return_value=[f"key_{i}" for i in range(5)]
        )

        mock_s3_client.delete_vectors.side_effect = Exception("Delete failed")

        result = vector_store.delete_all_vectors()

        assert result["success"] is False
        assert result["vectors_deleted"] == 0
        assert result["vectors_failed"] == 5
        assert "Failed to delete any vectors" in result["message"]

    @pytest.mark.parametrize("has_exception,expected_keys", [
        (False, ['vector1', 'vector2']),  # Success
        (True, []),  # Exception
    ])
    def test_get_all_vector_keys_scenarios(
        self,
        vector_store,
        mock_s3_client,
        has_exception,
        expected_keys
    ):
        if has_exception:
            mock_s3_client.get_paginator.side_effect = Exception("Paginator error")
        else:
            mock_page = {
                'vectors': [
                    {'key': 'vector1'},
                    {'key': 'vector2'},
                    {'key': None}
                ]
            }
            mock_paginator = MagicMock()
            mock_paginator.paginate.return_value = [mock_page]
            mock_s3_client.get_paginator.return_value = mock_paginator

        keys = vector_store._get_all_vector_keys()

        assert keys == expected_keys
        if not has_exception:
            mock_s3_client.get_paginator.assert_called_with('list_vectors')

    def test_delete_documents_by_source_id_partial_success(
        self,
        vector_store,
        mock_s3_client,
        mocker
    ):
        mocker.patch.object(
            vector_store,
            '_get_vector_keys_by_source_id',
            return_value=[f"key_{i}" for i in range(150)]
        )


        mock_s3_client.delete_vectors.side_effect = [
            {"ResponseMetadata": {"HTTPStatusCode": 200}},
            Exception("Delete failed")
        ]

        result = vector_store.delete_documents_by_source_id("test123")

        assert result["success"] is False
        assert result["vectors_deleted"] == 100
        assert result["vectors_failed"] == 50
        assert "Partially successful" in result["message"]

    def test_delete_documents_by_source_id_complete_failure(
        self,
        vector_store,
        mock_s3_client,
        mocker
    ):
        mocker.patch.object(
            vector_store,
            '_get_vector_keys_by_source_id',
            return_value=[f"key_{i}" for i in range(3)]
        )

        mock_s3_client.delete_vectors.side_effect = Exception("Delete failed")

        result = vector_store.delete_documents_by_source_id("test123")

        assert result["success"] is False
        assert result["vectors_deleted"] == 0
        assert result["vectors_failed"] == 3
        assert "Failed to delete any vectors" in result["message"]

    def test_delete_documents_by_source_id_get_keys_exception(
        self,
        vector_store,
        mocker
    ):
        mocker.patch.object(
            vector_store,
            '_get_vector_keys_by_source_id',
            side_effect=Exception("Get keys failed")
        )

        result = vector_store.delete_documents_by_source_id("test123")

        assert result["success"] is False
        assert result["vectors_found"] == 0
        assert "Deletion process failed" in result["message"]

    @pytest.mark.parametrize("has_exception,expected_count", [
        (False, 2),  # Success
        (True, 0),   # Exception
    ])
    def test_iterate_vectors_by_source_id_scenarios(
        self,
        vector_store,
        mock_s3_client,
        has_exception,
        expected_count
    ):
        if has_exception:
            mock_s3_client.get_paginator.side_effect = Exception("Paginator error")
        else:
            mock_page = {
                'vectors': [
                    {'key': 'vector1', 'metadata': {'source_id': 'test123'}},
                    {'key': 'vector2', 'metadata': {'source_id': 'other'}},
                    {'key': 'vector3', 'metadata': {'source_id': 'test123'}}
                ]
            }
            mock_paginator = MagicMock()
            mock_paginator.paginate.return_value = [mock_page]
            mock_s3_client.get_paginator.return_value = mock_paginator

        vectors = list(vector_store._iterate_vectors_by_source_id("test123"))

        assert len(vectors) == expected_count
        if not has_exception:
            assert vectors[0]['key'] == 'vector1'
            assert vectors[1]['key'] == 'vector3'

    def test_get_vector_keys_by_source_id(
        self,
        vector_store,
        mocker
    ):
        mock_vectors = [
            {'key': 'vector1'},
            {'key': 'vector2'},
            {'key': None}
        ]
        mocker.patch.object(
            vector_store,
            '_iterate_vectors_by_source_id',
            return_value=iter(mock_vectors)
        )

        keys = vector_store._get_vector_keys_by_source_id("test123")

        assert keys == ['vector1', 'vector2']
