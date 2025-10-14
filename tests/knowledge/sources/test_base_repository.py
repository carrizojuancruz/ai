import pytest

from app.knowledge.sources.base_repository import SourceRepositoryInterface


@pytest.mark.unit
class TestBaseRepository:

    def test_interface_methods_defined(self):
        required_methods = [
            'load_all',
            'find_by_id',
            'find_by_url',
            'add',
            'update',
            'upsert'
        ]

        for method in required_methods:
            assert hasattr(SourceRepositoryInterface, method)

    def test_concrete_implementation_required(self):
        with pytest.raises(TypeError):
            SourceRepositoryInterface()
