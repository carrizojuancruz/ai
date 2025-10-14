from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_vector_response():
    return {
        'vectors': [
            {
                'key': 'doc_test123_hash456_0',
                'metadata': {
                    'source_id': 'test123',
                    'content': 'Test content',
                    'content_hash': 'hash456',
                    'section_url': 'https://example.com/page1',
                    'source_url': 'https://example.com',
                    'name': 'Test Source',
                    'type': 'article',
                    'category': 'finance',
                    'description': 'Test description',
                    'chunk_index': 0
                },
                'distance': 0.2
            }
        ]
    }


@pytest.fixture
def mock_paginator(mocker):
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [
        {
            'vectors': [
                {'key': f'doc_key_{i}', 'metadata': {'source_id': 'test123'}}
                for i in range(100)
            ]
        }
    ]
    return mock_paginator
