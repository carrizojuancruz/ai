"""Application logging configuration."""

import contextlib
import logging
import os

DEFAULT_LOG_LEVEL = "INFO"


def configure_logging(level: str | None = None) -> None:
    """Configure root logger with a consistent format.

    Respects LOG_LEVEL env var; defaults to INFO.
    """
    log_level = (level or os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL)).upper()
    simple = os.getenv("LOG_SIMPLE", "").lower() in {"1", "true", "yes", "on"}
    fmt = os.getenv(
        "LOG_FORMAT",
        "%(message)s" if simple else "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    datefmt = os.getenv("LOG_DATEFMT", "%Y-%m-%dT%H:%M:%S%z")

    root = logging.getLogger()
    if root.handlers:
        for h in list(root.handlers):
            root.removeHandler(h)

    logging.basicConfig(level=log_level, format=fmt, datefmt=datefmt)

    if os.getenv("LOG_QUIET_LIBS", "").lower() in {"1", "true", "yes", "on"}:
        for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access", "botocore", "boto3"):
            with contextlib.suppress(Exception):
                logging.getLogger(noisy).setLevel(os.getenv("LOG_LIB_LEVEL", "WARNING").upper())


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger."""
    return logging.getLogger(name)
