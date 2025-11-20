from typing import Optional

from boto3.session import Session

from app.core.config import config
from app.repositories.s3_vectors_store import S3VectorsStore


def create_s3_vectors_store_from_env(
    *,
    region_name: Optional[str] = None,
    bucket_name: Optional[str] = None,
    index_name: Optional[str] = None,
    session: Optional[Session] = None,
) -> S3VectorsStore:
    """Create an S3VectorsStore using environment variables.

    Required env vars:
      - S3V_BUCKET (unless bucket_name is provided)
      - S3V_INDEX_MEMORY (unless index_name is provided)

    Optional env vars:
      - AWS_REGION (default: us-east-1 if not provided via region_name)
      - S3V_DISTANCE (default: cosine)
      - S3V_DIMS (default: 1024)
      - BEDROCK_EMBED_MODEL_ID

    Args:
        region_name: Optional AWS region override
        bucket_name: Optional S3 bucket name override (takes precedence over S3V_BUCKET env var)
        index_name: Optional index name override (takes precedence over S3V_INDEX_MEMORY env var)
        session: Optional boto3 Session override for credential/profile selection

    """
    bucket = bucket_name or config.S3V_BUCKET
    index = index_name or config.S3V_INDEX_MEMORY
    if not bucket or not index:
        raise RuntimeError("Missing S3V_BUCKET or S3V_INDEX_MEMORY environment variables")

    region = region_name or config.get_aws_region()
    distance = config.S3V_DISTANCE
    dims = config.S3V_DIMS
    model_id = config.BEDROCK_EMBED_MODEL_ID

    boto_session = session or Session()
    s3v = boto_session.client("s3vectors", region_name=region)
    bedrock = boto_session.client("bedrock-runtime", region_name=region)

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


