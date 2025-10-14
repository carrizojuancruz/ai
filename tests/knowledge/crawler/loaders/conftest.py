from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_playwright():
    mock_page = MagicMock()
    mock_page.content.return_value = "<html><body>Test content</body></html>"
    mock_page.goto.return_value = None
    mock_page.wait_for_timeout.return_value = None
    mock_page.set_extra_http_headers.return_value = None

    mock_browser = MagicMock()
    mock_browser.new_page.return_value = mock_page
    mock_browser.close.return_value = None

    mock_playwright_instance = MagicMock()
    mock_playwright_instance.chromium.launch.return_value = mock_browser

    with patch(
        'app.knowledge.crawler.loaders.single_page_loader.sync_playwright'
    ) as mock_sync_playwright:
        mock_sync_playwright.return_value.__enter__.return_value = mock_playwright_instance
        yield mock_page
