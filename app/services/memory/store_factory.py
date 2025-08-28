from typing import Optional

import boto3

from app.core.config import config
from app.repositories.s3_vectors_store import S3VectorsStore


def create_s3_vectors_store_from_env(
    *,
    region_name: Optional[str] = None,
) -> S3VectorsStore:
    """Create an S3VectorsStore using environment variables.

    Required env vars:
      - S3V_BUCKET
      - S3V_INDEX

    Optional env vars:
      - AWS_REGION (default: us-east-1 if not provided via region_name)
      - S3V_DISTANCE (default: cosine)
      - S3V_DIMS (default: 1024)
      - BEDROCK_EMBED_MODEL_ID (default: amazon.titan-embed-text-v2:0)
    """
    bucket = config.S3V_BUCKET
    index = config.S3V_INDEX_MEMORY
    if not bucket or not index:
        raise RuntimeError("Missing S3V_BUCKET or S3V_INDEX environment variables")

    region = region_name or config.get_aws_region()
    distance = config.S3V_DISTANCE
    dims = config.S3V_DIMS
    model_id = config.BEDROCK_EMBED_MODEL_ID

    s3v = boto3.client("s3vectors", region_name=region)
    bedrock = boto3.client("bedrock-runtime", region_name=region)

    return S3VectorsStore(
        s3v_client=s3v,
        bedrock_client=bedrock,
        vector_bucket_name=bucket,
        index_name=index,
        dims=dims,
        model_id=model_id,
        distance=distance,  # type: ignore[arg-type]
        default_index_fields=["summary"],
    )


