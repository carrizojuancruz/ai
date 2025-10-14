"""Tests for S3VectorsStore."""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from app.repositories.s3_vectors_store import (
    S3VectorsStore,
    _compose_point_uuid,
    _extract_by_field_paths,
    _flatten_all_strings,
    _join_namespace,
    _utc_now_iso,
    get_s3_vectors_store,
)


@pytest.fixture
def mock_s3v_client():
    """Create mock S3 Vectors client."""
    client = MagicMock()
    client.put_vectors = MagicMock()
    client.query_vectors = MagicMock()
    client.delete_vectors = MagicMock()
    client.get_vectors = MagicMock()
    return client


@pytest.fixture
def mock_bedrock_client():
    """Create mock Bedrock client for embeddings."""
    client = MagicMock()
    mock_body = MagicMock()
    mock_body.read.return_value = json.dumps({"embedding": [0.1] * 1024})
    client.invoke_model.return_value = {"body": mock_body}
    return client


@pytest.fixture
def sample_namespace():
    """Sample namespace tuple."""
    return ("user-123", "semantic")


@pytest.fixture
def sample_value():
    """Sample value dictionary."""
    return {
        "summary": "Test memory",
        "importance": 1,
        "category": "finance",
        "topic_key": "investments",
    }


@pytest.fixture
def s3_store(mock_s3v_client, mock_bedrock_client):
    """Create S3VectorsStore instance with mocked clients."""
    return S3VectorsStore(
        s3v_client=mock_s3v_client,
        bedrock_client=mock_bedrock_client,
        vector_bucket_name="test-bucket",
        index_name="test-index",
        dims=1024,
        model_id="amazon.titan-embed-text-v1",
        distance="COSINE",
        default_index_fields=["summary"],
    )


class TestUtilityFunctions:
    """Test module-level utility functions."""

    def test_utc_now_iso_returns_valid_iso_string(self):
        """Test that _utc_now_iso returns valid ISO format."""
        result = _utc_now_iso()

        assert isinstance(result, str)
        assert "T" in result
        datetime.fromisoformat(result)

    def test_join_namespace(self):
        """Test _join_namespace joins with pipe separator."""
        assert _join_namespace(("user-123",)) == "user-123"
        assert _join_namespace(("user-123", "semantic")) == "user-123|semantic"
        assert _join_namespace(()) == ""

    def test_compose_point_uuid_is_deterministic(self):
        """Test that _compose_point_uuid generates deterministic UUIDs."""
        uuid1 = _compose_point_uuid(("user-123", "semantic"), "key-001")
        uuid2 = _compose_point_uuid(("user-123", "semantic"), "key-001")
        uuid3 = _compose_point_uuid(("user-123", "semantic"), "key-002")

        assert uuid1 == uuid2
        assert uuid1 != uuid3
        assert isinstance(uuid1, UUID)

    def test_flatten_all_strings(self):
        """Test _flatten_all_strings extracts all string values."""
        data = {
            "user": {"name": "Alice", "city": "NYC"},
            "tags": ["tag1", "tag2"],
            "count": 42,
        }

        result = _flatten_all_strings(data)

        assert "Alice" in result
        assert "NYC" in result
        assert "tag1" in result
        assert "tag2" in result

    def test_extract_by_field_paths_with_nested_and_arrays(self):
        """Test _extract_by_field_paths with various path types."""
        value = {
            "summary": "Test",
            "user": {"name": "Alice"},
            "tags": ["tag1", "tag2"],
            "items": ["first", "second"],
        }

        assert _extract_by_field_paths(value, ["summary"]) == ["Test"]
        assert _extract_by_field_paths(value, ["user.name"]) == ["Alice"]
        assert "tag1" in _extract_by_field_paths(value, ["tags[*]"])
        assert _extract_by_field_paths(value, ["items[0]"]) == ["first"]
        assert "Test" in _extract_by_field_paths(value, ["$"])


class TestS3VectorsStoreInitialization:
    """Test S3VectorsStore initialization."""

    def test_initialization_with_all_parameters_and_defaults(self, mock_s3v_client, mock_bedrock_client):
        """Test initialization with all parameters and defaults."""
        store = S3VectorsStore(
            s3v_client=mock_s3v_client,
            bedrock_client=mock_bedrock_client,
            vector_bucket_name="my-bucket",
            index_name="my-index",
            dims=1024,
            model_id="test-model",
            distance="EUCLIDEAN",
            default_index_fields=["summary", "content"],
        )

        assert store._s3v is mock_s3v_client
        assert store._bedrock is mock_bedrock_client
        assert store._bucket == "my-bucket"
        assert store._index == "my-index"
        assert store._dims == 1024
        assert store._model_id == "test-model"
        assert store._distance == "EUCLIDEAN"
        assert store._default_index_fields == ["summary", "content"]
        assert store.supports_ttl is False

        store_with_defaults = S3VectorsStore(
            s3v_client=mock_s3v_client,
            bedrock_client=mock_bedrock_client,
            vector_bucket_name="bucket",
            index_name="index",
            dims=512,
            model_id="model",
        )

        assert store_with_defaults._distance == "COSINE"
        assert store_with_defaults._default_index_fields == ["summary"]


class TestPutOperations:
    """Test put operations."""

    def test_put_creates_vector_with_indexed_content(self, s3_store, sample_namespace, sample_value):
        """Test put creates vector with indexed content."""
        s3_store.put(sample_namespace, "key-001", sample_value)

        s3_store._s3v.put_vectors.assert_called_once()
        call_args = s3_store._s3v.put_vectors.call_args
        vectors = call_args[1]["vectors"]
        vector = vectors[0]
        metadata = vector["metadata"]

        assert metadata["doc_key"] == "key-001"
        assert metadata["ns_0"] == "user-123"
        assert metadata["ns_1"] == "semantic"
        assert metadata["is_indexed"] is True
        assert metadata["category"] == "finance"
        assert "value_json" in metadata

    def test_put_with_index_false_creates_zero_vector(self, s3_store, sample_namespace, sample_value):
        """Test put with index=False creates zero vector."""
        s3_store.put(sample_namespace, "key-002", sample_value, index=False)

        call_args = s3_store._s3v.put_vectors.call_args
        vector = call_args[1]["vectors"][0]
        metadata = vector["metadata"]
        vector_data = vector["data"]["float32"]

        assert metadata["is_indexed"] is False
        assert all(v == 0.0 for v in vector_data)

    def test_put_with_empty_namespace(self, s3_store):
        """Test put with empty namespace."""
        s3_store.put((), "key-004", {"summary": "Test"})

        call_args = s3_store._s3v.put_vectors.call_args
        metadata = call_args[1]["vectors"][0]["metadata"]
        assert metadata["ns_0"] == ""
        assert metadata["ns_1"] == ""

    def test_put_preserves_created_at_from_value(self, s3_store, sample_namespace):
        """Test put preserves created_at if present in value."""
        created_at = "2024-01-01T00:00:00+00:00"
        value = {"summary": "Test", "created_at": created_at}

        s3_store.put(sample_namespace, "key-005", value)

        call_args = s3_store._s3v.put_vectors.call_args
        metadata = call_args[1]["vectors"][0]["metadata"]
        assert metadata["created_at"] == created_at


class TestGetOperations:
    """Test get operations."""

    def test_get_with_direct_key_fetch(self, s3_store, sample_namespace):
        """Test get using direct key fetch when available."""
        mock_vectors = [
            {
                "metadata": {
                    "value_json": json.dumps({"summary": "Test"}),
                    "doc_key": "key-001",
                    "created_at": "2024-01-01T00:00:00+00:00",
                    "updated_at": "2024-01-02T00:00:00+00:00",
                    "ns_0": "user-123",
                    "ns_1": "semantic",
                }
            }
        ]
        s3_store._s3v.get_vectors.return_value = {"vectors": mock_vectors}

        result = s3_store.get(sample_namespace, "key-001")

        assert result is not None
        assert result.key == "key-001"
        assert result.value == {"summary": "Test"}
        assert result.namespace == ("user-123", "semantic")

    def test_get_falls_back_to_query_when_direct_fails(self, s3_store, sample_namespace):
        """Test get falls back to query when direct key fetch fails."""
        s3_store._s3v.get_vectors.side_effect = Exception("Not available")

        mock_vectors = [
            {
                "metadata": {
                    "value_json": json.dumps({"summary": "Test"}),
                    "doc_key": "key-002",
                    "created_at": "2024-01-01T00:00:00+00:00",
                    "updated_at": "2024-01-02T00:00:00+00:00",
                    "ns_0": "user-123",
                    "ns_1": "semantic",
                }
            }
        ]
        s3_store._s3v.query_vectors.return_value = {"vectors": mock_vectors}

        result = s3_store.get(sample_namespace, "key-002")

        assert result is not None
        assert result.key == "key-002"

    def test_get_returns_none_when_not_found(self, s3_store, sample_namespace):
        """Test get returns None when item not found."""
        s3_store._s3v.get_vectors.return_value = {"vectors": []}

        result = s3_store.get(sample_namespace, "nonexistent")

        assert result is None

    def test_get_handles_invalid_json_in_value(self, s3_store, sample_namespace):
        """Test get handles invalid JSON gracefully."""
        mock_vectors = [
            {
                "metadata": {
                    "value_json": "invalid json {",
                    "doc_key": "key-003",
                    "ns_0": "user-123",
                }
            }
        ]
        s3_store._s3v.get_vectors.return_value = {"vectors": mock_vectors}

        result = s3_store.get(sample_namespace, "key-003")

        assert result is not None
        assert result.value == {}


class TestSearchOperations:
    """Test search operations."""

    def test_search_with_query(self, s3_store, sample_namespace):
        """Test search with query string."""
        mock_vectors = [
            {
                "metadata": {
                    "value_json": json.dumps({"summary": "Finance tip"}),
                    "doc_key": "mem-001",
                    "ns_0": "user-123",
                    "ns_1": "semantic",
                },
                "distance": 0.2,
            }
        ]
        s3_store._s3v.query_vectors.return_value = {"vectors": mock_vectors}

        results = s3_store.search(sample_namespace, query="finance")

        assert len(results) == 1
        assert results[0].key == "mem-001"
        assert results[0].score is not None

    def test_search_returns_empty_list_without_query(self, s3_store, sample_namespace):
        """Test search returns empty list when no query provided."""
        results = s3_store.search(sample_namespace, query=None)

        assert results == []

    def test_search_with_filter(self, s3_store, sample_namespace):
        """Test search with filter dictionary."""
        mock_vectors = []
        s3_store._s3v.query_vectors.return_value = {"vectors": mock_vectors}

        s3_store.search(
            sample_namespace,
            query="test",
            filter={"category": "finance"},
        )

        call_args = s3_store._s3v.query_vectors.call_args
        flt = call_args[1]["filter"]
        assert "category" in flt

    def test_search_with_limit_and_offset(self, s3_store, sample_namespace):
        """Test search with limit and offset."""
        mock_vectors = [
            {
                "metadata": {
                    "value_json": json.dumps({"summary": f"Item {i}"}),
                    "doc_key": f"key-{i}",
                    "ns_0": "user-123",
                },
                "distance": 0.1 * i,
            }
            for i in range(10)
        ]
        s3_store._s3v.query_vectors.return_value = {"vectors": mock_vectors}

        results = s3_store.search(sample_namespace, query="test", limit=3, offset=2)

        assert len(results) == 3
        assert results[0].key == "key-2"

    def test_search_calculates_cosine_score(self, s3_store, sample_namespace):
        """Test search calculates score for COSINE distance."""
        mock_vectors = [
            {
                "metadata": {
                    "value_json": json.dumps({}),
                    "doc_key": "key-001",
                    "ns_0": "user-123",
                },
                "distance": 0.3,
            }
        ]
        s3_store._s3v.query_vectors.return_value = {"vectors": mock_vectors}

        results = s3_store.search(sample_namespace, query="test")

        assert results[0].score == 0.7

    def test_search_calculates_euclidean_score(self, mock_s3v_client, mock_bedrock_client, sample_namespace):
        """Test search calculates score for EUCLIDEAN distance."""
        store = S3VectorsStore(
            s3v_client=mock_s3v_client,
            bedrock_client=mock_bedrock_client,
            vector_bucket_name="bucket",
            index_name="index",
            dims=1024,
            model_id="model",
            distance="EUCLIDEAN",
        )

        mock_vectors = [
            {
                "metadata": {
                    "value_json": json.dumps({}),
                    "doc_key": "key-001",
                    "ns_0": "user-123",
                },
                "distance": 1.0,
            }
        ]
        mock_s3v_client.query_vectors.return_value = {"vectors": mock_vectors}

        results = store.search(sample_namespace, query="test")

        assert results[0].score == 0.5


class TestDeleteOperations:
    """Test delete operations."""

    def test_delete_calls_delete_vectors(self, s3_store, sample_namespace):
        """Test delete calls delete_vectors when available."""
        s3_store.delete(sample_namespace, "key-001")

        s3_store._s3v.delete_vectors.assert_called_once()
        call_args = s3_store._s3v.delete_vectors.call_args
        assert call_args[1]["vectorBucketName"] == "test-bucket"
        assert call_args[1]["indexName"] == "test-index"

    def test_delete_falls_back_to_generic_delete(self, s3_store, sample_namespace):
        """Test delete falls back to generic delete method."""
        delattr(s3_store._s3v, "delete_vectors")
        s3_store._s3v.delete = MagicMock()

        s3_store.delete(sample_namespace, "key-002")

        s3_store._s3v.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_adelete_calls_delete(self, s3_store, sample_namespace):
        """Test adelete calls synchronous delete."""
        await s3_store.adelete(sample_namespace, "key-003")

        s3_store._s3v.delete_vectors.assert_called_once()


class TestBatchOperations:
    """Test batch operations."""

    def test_batch_with_mixed_operations(self, s3_store):
        """Test batch with mixed operation types."""
        s3_store._s3v.get_vectors.return_value = {"vectors": []}
        s3_store._s3v.query_vectors.return_value = {"vectors": []}

        ops = [
            MagicMock(op="put", args=(("user-123",), "key-1", {}), kwargs={}),
            MagicMock(op="get", args=(("user-123",), "key-1"), kwargs={}),
            MagicMock(op="search", args=(("user-123",),), kwargs={"query": "test"}),
            MagicMock(op="delete", args=(("user-123",), "key-1"), kwargs={}),
        ]

        results = s3_store.batch(ops)

        assert len(results) == 4

    def test_batch_raises_on_unsupported_operation(self, s3_store):
        """Test batch raises ValueError for unsupported operations."""
        ops = [MagicMock(op="unsupported_op", args=(), kwargs={})]

        with pytest.raises(ValueError, match="Unsupported op"):
            s3_store.batch(ops)


class TestPrivateMethods:
    """Test private helper methods."""

    def test_zero_vector_creates_correct_size(self, s3_store):
        """Test _zero_vector creates vector of correct dimensions."""
        vector = s3_store._zero_vector()

        assert len(vector) == 1024
        assert all(v == 0.0 for v in vector)

    def test_embed_texts_calls_bedrock_and_handles_dimensions(self, mock_s3v_client, mock_bedrock_client, s3_store):
        """Test _embed_texts calls Bedrock and handles multiple texts with dimension normalization."""
        embeddings = s3_store._embed_texts(["text1", "text2"])
        assert len(embeddings) == 2
        assert len(embeddings[0]) == 1024
        assert s3_store._bedrock.invoke_model.call_count == 2

        mock_body_short = MagicMock()
        mock_body_short.read.return_value = json.dumps({"embedding": [0.1] * 512})
        mock_bedrock_client.invoke_model.return_value = {"body": mock_body_short}

        store_short = S3VectorsStore(
            s3v_client=mock_s3v_client,
            bedrock_client=mock_bedrock_client,
            vector_bucket_name="bucket",
            index_name="index",
            dims=1024,
            model_id="model",
        )
        embeddings_padded = store_short._embed_texts(["test"])
        assert len(embeddings_padded[0]) == 1024

        mock_body_long = MagicMock()
        mock_body_long.read.return_value = json.dumps({"embedding": [0.1] * 2048})
        mock_bedrock_client.invoke_model.return_value = {"body": mock_body_long}

        store_long = S3VectorsStore(
            s3v_client=mock_s3v_client,
            bedrock_client=mock_bedrock_client,
            vector_bucket_name="bucket",
            index_name="index",
            dims=1024,
            model_id="model",
        )
        embeddings_truncated = store_long._embed_texts(["test"])
        assert len(embeddings_truncated[0]) == 1024

    def test_build_filter_comprehensive(self, s3_store):
        """Test _build_filter with namespace, user filter, None handling, and is_indexed control."""
        flt_basic = s3_store._build_filter(("user-123", "semantic"), None)
        assert flt_basic["ns_0"] == "user-123"
        assert flt_basic["ns_1"] == "semantic"
        assert flt_basic["is_indexed"] is True

        flt_user = s3_store._build_filter(
            ("user-123",),
            {"category": "finance", "importance_bin": "high"},
        )
        assert flt_user["category"] == "finance"
        assert flt_user["importance_bin"] == "high"

        flt_none = s3_store._build_filter(
            ("user-123",),
            {"category": "finance", "topic": None},
        )
        assert "category" in flt_none
        assert "topic" not in flt_none

        flt_no_indexed = s3_store._build_filter(
            ("user-123",),
            None,
            include_is_indexed=False,
        )
        assert "is_indexed" not in flt_no_indexed


class TestListNamespaces:
    """Test list_namespaces method."""

    def test_list_namespaces_returns_empty_list(self, s3_store):
        """Test list_namespaces always returns empty list."""
        result = s3_store.list_namespaces()
        assert result == []


class TestGetRandomRecentHighImportance:
    """Test get_random_recent_high_importance method."""

    def test_get_random_recent_high_importance_returns_high_importance_memory(self, s3_store):
        """Test method returns high importance memory."""
        mock_vectors = [
            {
                "metadata": {
                    "value_json": json.dumps({"summary": "High", "importance": 1}),
                    "doc_key": "mem-001",
                    "ns_0": "user-123",
                    "created_at": "2024-01-01T00:00:00+00:00",
                }
            }
        ]
        s3_store._s3v.query_vectors.return_value = {"vectors": mock_vectors}

        result = s3_store.get_random_recent_high_importance("user-123")

        assert result is not None
        assert result["importance"] == 1

    def test_get_random_recent_high_importance_falls_back_to_medium(self, s3_store):
        """Test method falls back to medium importance when no high found."""
        mock_vectors = [
            {
                "metadata": {
                    "value_json": json.dumps({"summary": "Med", "importance": 0}),
                    "doc_key": "mem-001",
                    "ns_0": "user-123",
                    "created_at": "2024-01-01T00:00:00+00:00",
                }
            }
        ]
        s3_store._s3v.query_vectors.return_value = {"vectors": mock_vectors}

        result = s3_store.get_random_recent_high_importance("user-123", fallback_to_med=True)

        assert result is not None

    def test_get_random_recent_high_importance_returns_none_when_empty(self, s3_store):
        """Test method returns None when no memories found."""
        s3_store._s3v.query_vectors.return_value = {"vectors": []}

        result = s3_store.get_random_recent_high_importance("user-123")

        assert result is None

    def test_get_random_recent_high_importance_sorts_by_priority(self, s3_store):
        """Test method sorts candidates by priority."""
        mock_vectors = [
            {
                "metadata": {
                    "value_json": json.dumps({
                        "summary": "Low",
                        "importance": 0,
                        "importance_bin": "low",
                    }),
                    "doc_key": "mem-001",
                    "created_at": "2024-01-01T00:00:00+00:00",
                    "ns_0": "user-123",
                }
            },
            {
                "metadata": {
                    "value_json": json.dumps({
                        "summary": "High",
                        "importance": 2,
                        "importance_bin": "high",
                    }),
                    "doc_key": "mem-002",
                    "created_at": "2024-01-02T00:00:00+00:00",
                    "ns_0": "user-123",
                }
            },
        ]
        s3_store._s3v.query_vectors.return_value = {"vectors": mock_vectors}

        result = s3_store.get_random_recent_high_importance("user-123", fallback_to_med=True)

        assert result["importance"] == 2


class TestGetS3VectorsStore:
    """Test get_s3_vectors_store singleton function."""

    def test_get_s3_vectors_store_singleton_pattern(self):
        """Test get_s3_vectors_store creates and caches singleton instance."""
        with (
            patch("app.repositories.s3_vectors_store._s3_vectors_store_instance", None),
            patch("app.services.memory.store_factory.create_s3_vectors_store_from_env") as mock_create,
        ):
            mock_store = MagicMock()
            mock_create.return_value = mock_store

            result1 = get_s3_vectors_store()
            result2 = get_s3_vectors_store()

            assert result1 is mock_store
            assert result1 is result2
            mock_create.assert_called_once()
