import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class CrawlLogger:
    """Logger for tracking crawling results for external sources."""

    def __init__(self, log_file: Optional[str] = None):
        self.log_file = log_file or os.path.join(os.path.dirname(__file__), "log.txt")

    def _write_log(self, message: str) -> None:
        """Write a message to the crawl log file."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            logger.error(f"Failed to write to crawl log: {e}")

    def log_success(self, url: str, documents: int, chunks: int, is_new: bool) -> None:
        """Log successful crawling operation."""
        status = "CREATED" if is_new else "UPDATED"
        if chunks > 0:
            self._write_log(f"SUCCESS: {url} - {status} with {documents} documents, {chunks} chunks")
        else:
            self._write_log(f"NO_CHANGES: {url} - Source processed but no new content")

    def log_error(self, url: str, error: str, cause: Optional[str] = None) -> None:
        """Log failed crawling operation."""
        cause_info = f" ({cause})" if cause else ""
        self._write_log(f"ERROR: {url} - {error}{cause_info}")

    def log_deletion(self, url: str, success: bool) -> None:
        """Log source deletion operation."""
        status = "SUCCESS" if success else "ERROR"
        action = "Deleted obsolete source" if success else "Failed to delete source"
        self._write_log(f"{status}: {url} - {action}")

    def log_sync_start(self, total_sources: int, limited_sources: int) -> None:
        """Log sync operation start."""
        if limited_sources < total_sources:
            self._write_log(f"SYNC_START: Processing {limited_sources} of {total_sources} sources (limited)")
        else:
            self._write_log(f"SYNC_START: Processing {total_sources} sources")

    def log_sync_complete(self, created: int, updated: int, unchanged: int, deleted: int, errors: int, total_time: float) -> None:
        """Log sync operation completion."""
        self._write_log(
            f"SYNC_COMPLETE: Created {created}, Updated {updated}, Unchanged {unchanged}, "
            f"Deleted {deleted}, Errors {errors} - Total time: {total_time:.2f}s"
        )
