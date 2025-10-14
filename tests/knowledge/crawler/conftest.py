from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_recursive_loader(mocker):
    mock = mocker.patch('app.knowledge.crawler.loaders.recursive_loader.RecursiveUrlLoader')
    mock_instance = MagicMock()
    mock_instance.load.return_value = []
    mock.return_value = mock_instance
    return mock_instance


@pytest.fixture
def mock_sitemap_loader(mocker):
    mock = mocker.patch('app.knowledge.crawler.loaders.sitemap_loader.LangchainSitemapLoader')
    mock_instance = MagicMock()
    mock_instance.load.return_value = []
    mock.return_value = mock_instance
    return mock_instance


@pytest.fixture
def mock_pdf_loader(mocker):
    mock = mocker.patch('app.knowledge.crawler.loaders.pdf_loader.PyPDFLoader')
    mock_instance = MagicMock()
    mock_instance.load.return_value = []
    mock.return_value = mock_instance
    return mock_instance
