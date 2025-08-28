"""TODO: Sacar esto y reemplazarlo por el config ubicado en core."""
from dotenv import load_dotenv

from app.core.config import config

load_dotenv()

CHUNK_SIZE = config.CHUNK_SIZE
CHUNK_OVERLAP = config.CHUNK_OVERLAP
TOP_K_SEARCH = config.TOP_K_SEARCH

CRAWL_TYPE = config.CRAWL_TYPE
CRAWL_MAX_DEPTH = config.CRAWL_MAX_DEPTH
CRAWL_MAX_PAGES = config.CRAWL_MAX_PAGES
CRAWL_TIMEOUT = config.CRAWL_TIMEOUT

S3_VECTOR_NAME = config.S3_VECTOR_NAME
VECTOR_INDEX_NAME = config.VECTOR_INDEX_NAME
EMBEDDINGS_MODEL_ID = config.EMBEDDINGS_MODEL_ID
AWS_REGION = config.get_aws_region()

SOURCES_FILE_PATH = "./app/knowledge/sources/sources.json"
