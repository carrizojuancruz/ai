from pathlib import Path

import pytest

from app.knowledge.crawl_logger import CrawlLogger


@pytest.mark.unit
class TestCrawlLogger:

    @pytest.fixture
    def temp_log_file(self, tmp_path):
        log_file = tmp_path / "test_crawl.log"
        log_file.touch()
        return str(log_file)

    @pytest.fixture
    def logger(self, temp_log_file):
        return CrawlLogger(temp_log_file)

    @pytest.mark.parametrize("documents,chunks,is_new,expected_status,expected_count", [
        (2, 10, True, "CREATED", "2 documents"),
        (1, 5, False, "UPDATED", "1 documents"),
        (1, 0, False, "NO_CHANGES", None),
    ])
    def test_log_success_scenarios(self, logger, temp_log_file, documents, chunks, is_new, expected_status, expected_count):
        logger.log_success("https://example.com", documents=documents, chunks=chunks, is_new=is_new)

        log_content = Path(temp_log_file).read_text()
        if expected_status != "NO_CHANGES":
            assert "SUCCESS" in log_content
        assert expected_status in log_content
        if expected_count:
            assert expected_count in log_content
            assert f"{chunks} chunks" in log_content
        assert "https://example.com" in log_content

    @pytest.mark.parametrize("cause,expected_in_log", [
        ("Timeout error", "Timeout error"),
        (None, None),
    ])
    def test_log_error_scenarios(self, logger, temp_log_file, cause, expected_in_log):
        logger.log_error("https://example.com", "Connection timeout", cause=cause)

        log_content = Path(temp_log_file).read_text()
        assert "ERROR" in log_content
        assert "https://example.com" in log_content
        assert "Connection timeout" in log_content
        if expected_in_log:
            assert expected_in_log in log_content

    @pytest.mark.parametrize("success,expected_status,expected_message", [
        (True, "SUCCESS", "Deleted obsolete source"),
        (False, "ERROR", "Failed to delete source"),
    ])
    def test_log_deletion_scenarios(self, logger, temp_log_file, success, expected_status, expected_message):
        logger.log_deletion("https://example.com", success=success)

        log_content = Path(temp_log_file).read_text()
        assert expected_status in log_content
        assert expected_message in log_content

    def test_log_sync_start(self, logger, temp_log_file):
        logger.log_sync_start(total_sources=10, limited_sources=5)

        log_content = Path(temp_log_file).read_text()
        assert "SYNC_START" in log_content
        assert "10" in log_content
        assert "5" in log_content

    def test_log_sync_complete(self, logger, temp_log_file):
        logger.log_sync_complete(
            created=3,
            updated=2,
            unchanged=2,
            deleted=1,
            errors=1,
            total_time=120.5
        )

        log_content = Path(temp_log_file).read_text()
        assert "SYNC_COMPLETE" in log_content
        assert "3" in log_content
        assert "120.5" in log_content

    def test_timestamp_format(self, logger, temp_log_file):
        logger.log_success("https://example.com", "Test", is_new=True, chunks=1)

        log_content = Path(temp_log_file).read_text()
        assert "[" in log_content
        assert "]" in log_content

    def test_log_file_creation(self, tmp_path):
        log_path = tmp_path / "new_log.txt"
        logger = CrawlLogger(str(log_path))

        logger.log_success("https://example.com", "Test", is_new=True, chunks=1)

        assert log_path.exists()
