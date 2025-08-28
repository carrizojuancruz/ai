"""Application logging configuration."""

import contextlib
import logging

from app.core.config import config

DEFAULT_LOG_LEVEL = "INFO"


def configure_logging(level: str | None = None) -> None:
    """Configure root logger with a consistent format.

    Respects LOG_LEVEL env var; defaults to INFO.
    """
    log_level = (level or config.LOG_LEVEL).upper()
    simple = config.LOG_SIMPLE
    fmt = "%(message)s" if simple else "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    datefmt = config.LOG_DATEFMT

    root = logging.getLogger()
    if root.handlers:
        for h in list(root.handlers):
            root.removeHandler(h)

    logging.basicConfig(level=log_level, format=fmt, datefmt=datefmt)

    if config.LOG_QUIET_LIBS:
        for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access", "botocore", "boto3"):
            with contextlib.suppress(Exception):
                logging.getLogger(noisy).setLevel(config.LOG_LIB_LEVEL)


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger."""
    return logging.getLogger(name)
