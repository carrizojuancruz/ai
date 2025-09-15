from unittest.mock import patch

import pytest

from app.knowledge.sources.repository import SourceRepository


class TestSourceRepository:

    @pytest.fixture
    def repository(self, mock_external_services):
        with patch('app.knowledge.sources.repository.appConfig.SOURCES_FILE_PATH', '/tmp/test_sources.json'):
            return SourceRepository()

    def test_load_all_sources(self, repository):
        sources = repository.load_all()
        assert isinstance(sources, list)

    def test_find_by_url(self, repository, sample_source):
        repository.add(sample_source)
        found = repository.find_by_url(sample_source.url)
        assert found is not None
        assert found.url == sample_source.url

    def test_add_and_find_by_id(self, repository, sample_source):
        repository.add(sample_source)
        found = repository.find_by_id(sample_source.id)
        assert found is not None
        assert found.id == sample_source.id

    def test_upsert_new_source(self, repository, sample_source):
        repository.upsert(sample_source)
        found = repository.find_by_url(sample_source.url)
        assert found is not None

    def test_upsert_existing_source(self, repository, sample_source):
        repository.add(sample_source)
        sample_source.name = "Updated Name"
        repository.upsert(sample_source)
        found = repository.find_by_url(sample_source.url)
        assert found.name == "Updated Name"

    def test_delete_by_url(self, repository, sample_source):
        repository.add(sample_source)
        result = repository.delete_by_url(sample_source.url)
        assert result is True