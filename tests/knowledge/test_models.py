from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.knowledge.models import Source


@pytest.mark.unit
class TestSourceModel:

    def test_source_creation_with_minimal_fields(self):
        source = Source(
            id="test123",
            name="Test Source",
            url="https://example.com"
        )

        assert source.id == "test123"
        assert source.name == "Test Source"
        assert source.url == "https://example.com"
        assert source.enabled is True
        assert source.total_chunks == 0
        assert source.section_urls is None

    def test_source_creation_with_all_fields(self):
        now = datetime.now(UTC)
        source = Source(
            id="test_source_456",
            name="Multi-Section Source",
            url="https://example.com/main",
            enabled=True,
            type="guide",
            category="education",
            description="Test description",
            section_urls=["https://example.com/s1", "https://example.com/s2"],
            total_chunks=15,
            last_sync=now
        )

        assert source.id == "test_source_456"
        assert source.type == "guide"
        assert source.category == "education"
        assert source.description == "Test description"
        assert len(source.section_urls) == 2
        assert source.total_chunks == 15
        assert source.last_sync == now

    @pytest.mark.parametrize("url", [
        "https://example.com",
        "http://example.com/page",
        "https://example.com/document.pdf",
        "https://example.com/path/to/resource"
    ])
    def test_source_url_validation(self, url):
        source = Source(id="test", name="Test", url=url)
        assert source.url == url

    def test_source_serialization(self):
        now = datetime.now(UTC)
        source = Source(
            id="test_source_456",
            name="Multi-Section Source",
            url="https://example.com/main",
            enabled=True,
            type="guide",
            section_urls=["https://example.com/s1"],
            total_chunks=15,
            last_sync=now
        )

        data = source.model_dump(mode='json')

        assert data["id"] == "test_source_456"
        assert data["name"] == "Multi-Section Source"
        assert data["url"] == "https://example.com/main"
        assert "last_sync" in data
        assert isinstance(data["section_urls"], list)

    def test_source_missing_required_fields(self):
        with pytest.raises(ValidationError):
            Source(name="No ID", url="https://example.com")
        with pytest.raises(ValidationError):
            Source(id="x", url="https://example.com")
        with pytest.raises(ValidationError):
            Source(id="x", name="No URL")

    def test_source_json_round_trip(self):
        now = datetime.now(UTC)
        original = Source(
            id="rt1",
            name="Round Trip",
            url="https://example.com/rt",
            enabled=False,
            type="article",
            section_urls=["https://example.com/s1"],
            total_chunks=7,
            last_sync=now,
        )
        data = original.model_dump(mode="json")
        restored = Source(**data)

        assert restored.id == original.id
        assert restored.url == original.url
        assert restored.enabled is False
        assert restored.section_urls == original.section_urls
        assert restored.total_chunks == original.total_chunks
        assert restored.last_sync == original.last_sync

    def test_source_deserialization(self):
        data = {
            "id": "deserialize_test",
            "name": "Deserialized Source",
            "url": "https://example.com",
            "enabled": False,
            "type": "article"
        }

        source = Source(**data)
        assert source.id == "deserialize_test"
        assert source.enabled is False
        assert source.total_chunks == 0

    @pytest.mark.parametrize("section_urls,expected", [
        (None, None),
        ([], []),
        (["https://example.com/s1"], ["https://example.com/s1"]),
        (["https://example.com/s1", "https://example.com/s2"],
         ["https://example.com/s1", "https://example.com/s2"])
    ])
    def test_section_urls_list_handling(self, section_urls, expected):
        source = Source(
            id="test",
            name="Test",
            url="https://example.com",
            section_urls=section_urls
        )
        assert source.section_urls == expected

    def test_source_datetime_handling(self):
        now = datetime.now(UTC)
        source = Source(
            id="test",
            name="Test",
            url="https://example.com",
            last_sync=now
        )
        assert source.last_sync == now
        assert isinstance(source.last_sync, datetime)
