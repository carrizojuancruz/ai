import os
from dotenv import load_dotenv

load_dotenv()


def _get_env(key: str) -> str:
    """Get required environment variable."""
    value = os.getenv(key)
    if value is None:
        raise ValueError(f"Environment variable {key} is required")
    return value


def _get_int_env(key: str) -> int:
    """Get required environment variable as integer."""
    value = os.getenv(key)
    if value is None:
        raise ValueError(f"Environment variable {key} is required")
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"Environment variable {key} must be a valid integer, got: {value}")


# Document processing
CHUNK_SIZE = _get_int_env("CHUNK_SIZE")
CHUNK_OVERLAP = _get_int_env("CHUNK_OVERLAP")

# Crawler settings
CRAWL_TYPE = _get_env("CRAWL_TYPE")
CRAWL_MAX_DEPTH = _get_int_env("CRAWL_MAX_DEPTH")
CRAWL_MAX_PAGES = _get_int_env("CRAWL_MAX_PAGES")
CRAWL_TIMEOUT = _get_int_env("CRAWL_TIMEOUT")

# Vector store
S3_VECTOR_NAME = _get_env("S3_VECTOR_NAME")
VECTOR_INDEX_NAME = _get_env("VECTOR_INDEX_NAME")
TOP_K_SEARCH = _get_int_env("TOP_K_SEARCH")

# Embeddings
EMBEDDINGS_MODEL_ID = _get_env("EMBEDDINGS_MODEL_ID")

# AWS
AWS_REGION = _get_env("AWS_REGION")

# Sources
SOURCES_FILE_PATH = _get_env("SOURCES_FILE_PATH")
