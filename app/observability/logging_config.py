"""Application logging configuration."""

import contextlib
import logging

from app.core.config import config

DEFAULT_LOG_LEVEL = "INFO"


def configure_logging(level: str | None = None) -> None:
    """Configure root logger with a consistent format.

    Respects LOG_LEVEL env var; defaults to INFO.
    """
    if level:
        log_level = level.upper()
    elif config.LOG_LEVEL:
        log_level = config.LOG_LEVEL.upper()
    else:
        log_level = DEFAULT_LOG_LEVEL
    simple = config.LOG_SIMPLE
    fmt = "%(message)s" if simple else "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    datefmt = config.LOG_DATEFMT

    root = logging.getLogger()
    if root.handlers:
        for h in list(root.handlers):
            root.removeHandler(h)

    logging.basicConfig(level=log_level, format=fmt, datefmt=datefmt)

    if config.LOG_QUIET_LIBS:
        lib_level = config.LOG_LIB_LEVEL or "WARNING"
        for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access", "botocore", "boto3"):
            with contextlib.suppress(Exception):
                logging.getLogger(noisy).setLevel(lib_level)


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger."""
    return logging.getLogger(name)
