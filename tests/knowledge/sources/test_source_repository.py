import json
from datetime import UTC, datetime

import pytest

from app.knowledge.models import Source
from app.knowledge.sources.repository import SourceRepository


@pytest.mark.unit
class TestSourceRepository:

    @pytest.fixture
    def repository(self, tmp_path):
        sources_file = tmp_path / "sources.json"
        sources_file.write_text("[]")
        return SourceRepository(str(sources_file))

    def test_ensure_file_exists_creates_file(self, tmp_path):
        file_path = tmp_path / "new_sources.json"
        SourceRepository(str(file_path))

        assert file_path.exists()
        assert file_path.read_text() == "[]"

    def test_ensure_file_exists_creates_directory(self, tmp_path):
        file_path = tmp_path / "subdir" / "sources.json"
        SourceRepository(str(file_path))

        assert file_path.exists()
        assert file_path.parent.exists()

    def test_load_all_empty_file(self, repository):
        sources = repository.load_all()

        assert sources == []

    def test_load_all_with_sources(self, tmp_path, sources_json_content):
        file_path = tmp_path / "sources.json"
        file_path.write_text(json.dumps(sources_json_content))
        repo = SourceRepository(str(file_path))

        sources = repo.load_all()

        assert len(sources) == 2
        assert all(isinstance(s, Source) for s in sources)

    def test_load_all_corrupted_json(self, corrupted_json_file):
        repo = SourceRepository(corrupted_json_file)

        sources = repo.load_all()

        assert sources == []

    def test_save_all(self, repository, sample_source):
        sources = [sample_source]

        repository.save_all(sources)

        loaded = repository.load_all()
        assert len(loaded) == 1
        assert loaded[0].id == sample_source.id

    def test_save_all_datetime_serialization(self, repository):
        now = datetime.now(UTC)
        source = Source(
            id="test",
            name="Test",
            url="https://example.com",
            last_sync=now
        )

        repository.save_all([source])

        loaded = repository.load_all()
        assert loaded[0].last_sync is not None

    def test_find_by_id_exists(self, repository, sample_source):
        repository.save_all([sample_source])

        found = repository.find_by_id(sample_source.id)

        assert found is not None
        assert found.id == sample_source.id

    def test_find_by_id_not_found(self, repository):
        found = repository.find_by_id("nonexistent")

        assert found is None

    def test_find_by_url_exists(self, repository, sample_source):
        repository.save_all([sample_source])

        found = repository.find_by_url(sample_source.url)

        assert found is not None
        assert found.url == sample_source.url

    def test_find_by_url_not_found(self, repository):
        found = repository.find_by_url("https://nonexistent.com")

        assert found is None

    def test_add_source(self, repository, sample_source):
        repository.add(sample_source)

        sources = repository.load_all()
        assert len(sources) == 1
        assert sources[0].id == sample_source.id

    def test_update_source_exists(self, repository, sample_source):
        repository.add(sample_source)
        sample_source.name = "Updated Name"

        result = repository.update(sample_source)

        assert result is True
        loaded = repository.find_by_id(sample_source.id)
        assert loaded.name == "Updated Name"

    def test_update_source_not_exists(self, repository, sample_source):
        result = repository.update(sample_source)

        assert result is False

    def test_upsert_new_source(self, repository, sample_source):
        repository.upsert(sample_source)

        sources = repository.load_all()
        assert len(sources) == 1

    def test_upsert_existing_source(self, repository, sample_source):
        repository.add(sample_source)
        sample_source.total_chunks = 100

        repository.upsert(sample_source)

        loaded = repository.find_by_id(sample_source.id)
        assert loaded.total_chunks == 100

    def test_upsert_sets_last_sync(self, repository, sample_source):
        repository.upsert(sample_source)

        loaded = repository.find_by_id(sample_source.id)
        assert loaded.last_sync is not None

    def test_delete_by_url_exists(self, repository, sample_source):
        repository.add(sample_source)

        result = repository.delete_by_url(sample_source.url)

        assert result is True
        assert repository.find_by_url(sample_source.url) is None

    def test_delete_by_url_not_found(self, repository):
        result = repository.delete_by_url("https://nonexistent.com")

        assert result is False

    def test_delete_all(self, repository, sample_source):
        repository.add(sample_source)

        result = repository.delete_all()

        assert result is True
        assert repository.load_all() == []
