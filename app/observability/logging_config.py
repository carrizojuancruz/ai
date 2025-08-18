"""Application logging configuration."""

import logging
import os

DEFAULT_LOG_LEVEL = "INFO"


def configure_logging(level: str | None = None) -> None:
    """Configure root logger with a consistent format.

    Respects LOG_LEVEL env var; defaults to INFO.
    """
    log_level = (level or os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL)).upper()
    fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S%z"

    root = logging.getLogger()
    if root.handlers:
        for h in list(root.handlers):
            root.removeHandler(h)

    logging.basicConfig(level=log_level, format=fmt, datefmt=datefmt)


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger."""
    return logging.getLogger(name)
