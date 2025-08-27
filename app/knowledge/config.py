import os

from dotenv import load_dotenv

load_dotenv()

CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "1500"))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "200"))
TOP_K_SEARCH = int(os.environ.get("TOP_K_SEARCH", "10"))

CRAWL_TYPE = os.environ.get("CRAWL_TYPE", "recursive")
CRAWL_MAX_DEPTH = int(os.environ.get("CRAWL_MAX_DEPTH", "3"))
CRAWL_MAX_PAGES = int(os.environ.get("CRAWL_MAX_PAGES", "50"))
CRAWL_TIMEOUT = int(os.environ.get("CRAWL_TIMEOUT", "30"))

S3_VECTOR_NAME = os.environ["S3_VECTOR_NAME"]
VECTOR_INDEX_NAME = os.environ["VECTOR_INDEX_NAME"]
EMBEDDINGS_MODEL_ID = os.environ["EMBEDDINGS_MODEL_ID"]
AWS_REGION = os.environ["AWS_REGION"]

SOURCES_FILE_PATH = "./app/knowledge/sources/sources.json"


