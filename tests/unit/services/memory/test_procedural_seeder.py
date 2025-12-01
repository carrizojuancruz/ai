"""Tests for procedural memory seeder."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.services.memory.procedural_seeder import (
    SUPERVISOR_PROCEDURAL_INDEX_FIELDS,
    SUPERVISOR_PROCEDURAL_NAMESPACE,
    ProceduralMemorySeeder,
    get_procedural_seeder,
)


class TestProceduralMemorySeeder:
    """Test ProceduralMemorySeeder class."""

    def test_init_default_base_path(self):
        """Test initialization with default base path."""
        seeder = ProceduralMemorySeeder()
        assert seeder.base_path is not None
        assert len(seeder.procedural_files) == 2

    def test_init_custom_base_path(self):
        """Test initialization with custom base path."""
        custom_path = Path("/custom/path")
        seeder = ProceduralMemorySeeder(base_path=custom_path)
        assert seeder.base_path == custom_path

    @pytest.mark.asyncio
    @patch("app.services.memory.procedural_seeder.create_s3_vectors_store_from_env")
    async def test_seed_supervisor_procedurals_store_creation_fails(self, mock_store_factory):
        """Test seeding when store creation fails."""
        mock_store_factory.side_effect = Exception("S3 connection failed")

        seeder = ProceduralMemorySeeder()
        result = await seeder.seed_supervisor_procedurals()

        assert result.ok is False
        assert "S3 connection failed" in result.error

    @pytest.mark.asyncio
    @patch("app.services.memory.procedural_seeder.create_s3_vectors_store_from_env")
    async def test_seed_supervisor_procedurals_success(self, mock_store_factory, tmp_path):
        """Test successful seeding of procedural memories."""
        # Create mock store
        mock_store = MagicMock()
        mock_store.get.return_value = None  # Not used in implementation
        mock_store.list_by_namespace.return_value = []  # No existing items
        mock_store_factory.return_value = mock_store

        # Create test JSONL file
        test_file = tmp_path / "test_routing.jsonl"
        test_data = [
            {"key": "test_1", "summary": "Test routing example 1", "category": "Routing"},
            {"key": "test_2", "summary": "Test routing example 2", "category": "Routing"},
        ]

        with test_file.open("w", encoding="utf-8") as f:
            for item in test_data:
                f.write(json.dumps(item) + "\n")

        # Create seeder with test file
        seeder = ProceduralMemorySeeder(base_path=tmp_path)
        seeder.procedural_files = ["test_routing.jsonl"]

        result = await seeder.seed_supervisor_procedurals()

        assert result.ok is True
        assert result.total_items == 2
        assert len(result.created) == 2
        assert len(result.skipped) == 0

        # Verify store.put was called correctly
        assert mock_store.put.call_count == 2
        for call_args in mock_store.put.call_args_list:
            args, kwargs = call_args
            namespace, key, data = args
            assert namespace == SUPERVISOR_PROCEDURAL_NAMESPACE
            assert key in ["test_1", "test_2"]
            assert kwargs["index"] == SUPERVISOR_PROCEDURAL_INDEX_FIELDS

    @pytest.mark.asyncio
    @patch("app.services.memory.procedural_seeder.create_s3_vectors_store_from_env")
    async def test_seed_supervisor_procedurals_skip_existing(self, mock_store_factory, tmp_path):
        """Test that existing items with identical summaries are skipped."""
        # Create mock store with existing item
        mock_store = MagicMock()
        mock_store.list_by_namespace.return_value = [
            Mock(key="test_1", value={"summary": "Existing item", "category": "Routing"})
        ]
        mock_store_factory.return_value = mock_store

        # Create test JSONL file
        test_file = tmp_path / "test_routing.jsonl"
        test_data = [
            {"key": "test_1", "summary": "Existing item", "category": "Routing"},
            {"key": "test_2", "summary": "New item", "category": "Routing"},
        ]

        with test_file.open("w", encoding="utf-8") as f:
            for item in test_data:
                f.write(json.dumps(item) + "\n")

        seeder = ProceduralMemorySeeder(base_path=tmp_path)
        seeder.procedural_files = ["test_routing.jsonl"]

        result = await seeder.seed_supervisor_procedurals()

        assert result.ok is True
        assert len(result.created) == 1  # Only test_2 created
        assert len(result.skipped) == 1  # test_1 skipped

    @pytest.mark.asyncio
    @patch("app.services.memory.procedural_seeder.create_s3_vectors_store_from_env")
    async def test_seed_supervisor_procedurals_force_update(self, mock_store_factory, tmp_path):
        """Test that existing items with different summaries are updated."""
        # Create mock store with existing item
        mock_store = MagicMock()
        mock_store.list_by_namespace.return_value = [
            Mock(key="test_1", value={"summary": "Old summary", "category": "Routing"})
        ]
        mock_store_factory.return_value = mock_store

        # Create test JSONL file
        test_file = tmp_path / "test_routing.jsonl"
        test_data = [
            {"key": "test_1", "summary": "Updated item", "category": "Routing"},
        ]

        with test_file.open("w", encoding="utf-8") as f:
            for item in test_data:
                f.write(json.dumps(item) + "\n")

        seeder = ProceduralMemorySeeder(base_path=tmp_path)
        seeder.procedural_files = ["test_routing.jsonl"]

        result = await seeder.seed_supervisor_procedurals()

        assert result.ok is True
        assert len(result.updated) == 1  # Item was updated, not created
        assert len(result.created) == 0
        assert len(result.skipped) == 0
        assert mock_store.put.call_count == 1

    @pytest.mark.asyncio
    @patch("app.services.memory.procedural_seeder.create_s3_vectors_store_from_env")
    async def test_seed_supervisor_procedurals_category_change(self, mock_store_factory, tmp_path):
        """Test that category changes are detected and trigger updates."""
        mock_store = MagicMock()
        mock_store.list_by_namespace.return_value = [
            Mock(key="test_1", value={"summary": "Same summary", "category": "OldCategory"})
        ]
        mock_store_factory.return_value = mock_store

        test_file = tmp_path / "test_routing.jsonl"
        test_data = [
            {"key": "test_1", "summary": "Same summary", "category": "NewCategory"},
        ]

        with test_file.open("w", encoding="utf-8") as f:
            for item in test_data:
                f.write(json.dumps(item) + "\n")

        seeder = ProceduralMemorySeeder(base_path=tmp_path)
        seeder.procedural_files = ["test_routing.jsonl"]

        result = await seeder.seed_supervisor_procedurals()

        assert result.ok is True
        assert len(result.updated) == 1
        assert len(result.created) == 0
        assert len(result.skipped) == 0
        assert mock_store.put.call_count == 1

    @pytest.mark.asyncio
    @patch("app.services.memory.procedural_seeder.create_s3_vectors_store_from_env")
    async def test_seed_file_handles_invalid_json(self, mock_store_factory, tmp_path):
        """Test that invalid JSON lines are handled gracefully."""
        mock_store = MagicMock()
        mock_store.list_by_namespace.return_value = []
        mock_store_factory.return_value = mock_store

        # Create test file with invalid JSON
        test_file = tmp_path / "test_routing.jsonl"
        with test_file.open("w", encoding="utf-8") as f:
            f.write('{"key": "test_1", "summary": "Valid"}\n')
            f.write('{"invalid json without closing brace\n')
            f.write('{"key": "test_2", "summary": "Another valid"}\n')

        seeder = ProceduralMemorySeeder(base_path=tmp_path)
        seeder.procedural_files = ["test_routing.jsonl"]

        result = await seeder.seed_supervisor_procedurals()

        assert result.ok is True
        assert len(result.created) == 2  # Only valid items
        # Note: Current implementation doesn't track parsing errors, just skips them

    @pytest.mark.asyncio
    @patch("app.services.memory.procedural_seeder.create_s3_vectors_store_from_env")
    async def test_seed_file_missing_key(self, mock_store_factory, tmp_path):
        """Test that items missing 'key' field are skipped."""
        mock_store = MagicMock()
        mock_store.list_by_namespace.return_value = []
        mock_store_factory.return_value = mock_store

        # Create test file with item missing key
        test_file = tmp_path / "test_routing.jsonl"
        test_data = [
            {"key": "test_1", "summary": "Valid"},
            {"summary": "Missing key field"},  # No key
            {"key": "test_2", "summary": "Valid"},
        ]

        with test_file.open("w", encoding="utf-8") as f:
            for item in test_data:
                f.write(json.dumps(item) + "\n")

        seeder = ProceduralMemorySeeder(base_path=tmp_path)
        seeder.procedural_files = ["test_routing.jsonl"]

        result = await seeder.seed_supervisor_procedurals()

        assert result.ok is True
        assert len(result.created) == 2
        # Note: Current implementation doesn't track parsing errors, just skips them

    @pytest.mark.asyncio
    @patch("app.services.memory.procedural_seeder.create_s3_vectors_store_from_env")
    async def test_verify_procedurals_exist_success(self, mock_store_factory):
        """Test verification when procedurals exist."""
        mock_store = MagicMock()
        mock_results = [Mock(key="test_1"), Mock(key="test_2"), Mock(key="test_3")]
        mock_store.list_by_namespace.return_value = mock_results
        mock_store_factory.return_value = mock_store

        seeder = ProceduralMemorySeeder()
        result = await seeder.verify_procedurals_exist()

        assert result["ok"] is True
        assert result["count"] == 3
        assert result["sample_keys"] == ["test_1", "test_2", "test_3"]

    @pytest.mark.asyncio
    @patch("app.services.memory.procedural_seeder.create_s3_vectors_store_from_env")
    async def test_verify_procedurals_exist_empty(self, mock_store_factory):
        """Test verification when no procedurals exist."""
        mock_store = MagicMock()
        mock_store.list_by_namespace.return_value = []
        mock_store_factory.return_value = mock_store

        seeder = ProceduralMemorySeeder()
        result = await seeder.verify_procedurals_exist()

        assert result["ok"] is True
        assert result["count"] == 0
        assert result["sample_keys"] == []

    @pytest.mark.asyncio
    @patch("app.services.memory.procedural_seeder.create_s3_vectors_store_from_env")
    async def test_verify_procedurals_exist_error(self, mock_store_factory):
        """Test verification when an error occurs."""
        mock_store_factory.side_effect = Exception("Connection failed")

        seeder = ProceduralMemorySeeder()
        result = await seeder.verify_procedurals_exist()

        assert result["ok"] is False
        assert "Connection failed" in result["error"]
        assert result["count"] == 0

    @pytest.mark.asyncio
    @patch("app.services.memory.procedural_seeder.create_s3_vectors_store_from_env")
    async def test_seed_supervisor_procedurals_partial_failure(self, mock_store_factory, tmp_path):
        """Test that partial failures are tracked and don't stop the sync."""
        mock_store = MagicMock()
        mock_store.list_by_namespace.return_value = []

        def put_side_effect(namespace, key, data, index):
            if key == "test_2":
                raise Exception("S3 write error")

        mock_store.put.side_effect = put_side_effect
        mock_store_factory.return_value = mock_store

        test_file = tmp_path / "test_routing.jsonl"
        test_data = [
            {"key": "test_1", "summary": "Valid item 1", "category": "Routing"},
            {"key": "test_2", "summary": "Will fail", "category": "Routing"},
            {"key": "test_3", "summary": "Valid item 3", "category": "Routing"},
        ]

        with test_file.open("w", encoding="utf-8") as f:
            for item in test_data:
                f.write(json.dumps(item) + "\n")

        seeder = ProceduralMemorySeeder(base_path=tmp_path)
        seeder.procedural_files = ["test_routing.jsonl"]

        result = await seeder.seed_supervisor_procedurals()

        assert result.ok is True
        assert len(result.created) == 2
        assert len(result.failed) == 1

        failed_keys = [key for key, _ in result.failed]
        assert "test_2" in failed_keys
        assert any("S3 write error" in error for _, error in result.failed)

    @pytest.mark.asyncio
    @patch("app.services.memory.procedural_seeder.create_s3_vectors_store_from_env")
    async def test_seed_supervisor_procedurals_delete_failure(self, mock_store_factory, tmp_path):
        """Test that delete failures are tracked."""
        mock_store = MagicMock()
        mock_store.list_by_namespace.return_value = [
            Mock(key="orphan_1", value={"summary": "Should be deleted"}),
            Mock(key="orphan_2", value={"summary": "Should be deleted"}),
        ]

        def delete_side_effect(namespace, key):
            if key == "orphan_2":
                raise Exception("S3 delete error")

        mock_store.delete.side_effect = delete_side_effect
        mock_store_factory.return_value = mock_store

        test_file = tmp_path / "test_routing.jsonl"
        test_file.write_text("")

        seeder = ProceduralMemorySeeder(base_path=tmp_path)
        seeder.procedural_files = ["test_routing.jsonl"]

        result = await seeder.seed_supervisor_procedurals()

        assert result.ok is True
        assert len(result.deleted) == 1
        assert len(result.failed) == 1

        failed_keys = [key for key, _ in result.failed]
        assert "orphan_2" in failed_keys
        assert any("S3 delete error" in error for _, error in result.failed)

    def test_get_procedural_seeder_singleton(self):
        """Test that get_procedural_seeder returns same instance."""
        seeder1 = get_procedural_seeder()
        seeder2 = get_procedural_seeder()
        assert seeder1 is seeder2
