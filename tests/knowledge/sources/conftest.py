import pytest


@pytest.fixture
def sources_json_content():
    return [
        {
            "id": "source1",
            "name": "Source One",
            "url": "https://example1.com",
            "enabled": True,
            "type": "article",
            "category": "finance",
            "total_chunks": 10
        },
        {
            "id": "source2",
            "name": "Source Two",
            "url": "https://example2.com",
            "enabled": False,
            "type": "guide",
            "category": "education",
            "total_chunks": 5
        }
    ]


@pytest.fixture
def corrupted_json_file(tmp_path):
    file_path = tmp_path / "corrupted.json"
    file_path.write_text("{invalid json content")
    return str(file_path)
