import os
import logging

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)

LOCAL_UPLOAD_DIR = "uploads"
os.makedirs(LOCAL_UPLOAD_DIR, exist_ok=True)


def _get_s3_client():
    """Get an S3 client. Uses IAM role credentials in ECS (no keys needed)."""
    return boto3.client("s3", region_name=settings.aws_default_region)


def save_file(file_content: bytes, file_key: str) -> str:
    """
    Save a file. Returns the path/key for later retrieval.

    In production (S3_BUCKET_NAME set): uploads to S3.
    In development (no bucket): saves to local filesystem.
    """
    if settings.s3_bucket_name:
        s3 = _get_s3_client()
        s3.put_object(
            Bucket=settings.s3_bucket_name,
            Key=file_key,
            Body=file_content,
        )
        logger.info(f"Uploaded to S3: {file_key}")
        return file_key
    else:
        local_path = os.path.join(LOCAL_UPLOAD_DIR, file_key)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(file_content)
        logger.info(f"Saved locally: {local_path}")
        return local_path


def load_file(file_key: str) -> bytes:
    """
    Load a file by its key/path.

    Automatically detects S3 vs local based on config.
    """
    if settings.s3_bucket_name:
        s3 = _get_s3_client()
        response = s3.get_object(
            Bucket=settings.s3_bucket_name,
            Key=file_key,
        )
        return response["Body"].read()
    else:
        with open(file_key, "rb") as f:
            return f.read()


def get_local_path(file_key: str) -> str:
    """
    Get a local file path for processing.

    For S3: downloads to a temp location and returns that path.
    For local: returns the path directly.

    The caller should clean up the temp file after processing.
    """
    if settings.s3_bucket_name:
        import tempfile
        content = load_file(file_key)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.write(content)
        tmp.close()
        return tmp.name
    else:
        return file_key