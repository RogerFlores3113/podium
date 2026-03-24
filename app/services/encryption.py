import base64
import logging
from functools import lru_cache

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


def _get_kms_client():
    return boto3.client("kms", region_name=settings.aws_default_region)


def encrypt_api_key(plaintext_key: str) -> bytes:
    """
    Encrypt an API key using AWS KMS.

    Returns the ciphertext as bytes (store directly in DB).
    For local dev without KMS, falls back to base64 encoding (NOT SECURE —
    only for local development convenience).
    """
    if not settings.kms_key_id:
        # Local dev fallback — NOT SECURE, just for testing
        logger.warning("KMS not configured — using base64 encoding (NOT SECURE)")
        return base64.b64encode(plaintext_key.encode())

    try:
        kms = _get_kms_client()
        response = kms.encrypt(
            KeyId=settings.kms_key_id,
            Plaintext=plaintext_key.encode(),
        )
        return response["CiphertextBlob"]
    except ClientError as e:
        logger.error(f"KMS encryption failed: {e}")
        raise


def decrypt_api_key(ciphertext: bytes) -> str:
    """
    Decrypt an API key using AWS KMS.

    For local dev without KMS, falls back to base64 decoding.
    """
    if not settings.kms_key_id:
        return base64.b64decode(ciphertext).decode()

    try:
        kms = _get_kms_client()
        response = kms.decrypt(
            CiphertextBlob=ciphertext,
        )
        return response["Plaintext"].decode()
    except ClientError as e:
        logger.error(f"KMS decryption failed: {e}")
        raise


# Simple in-memory cache for decrypted keys (TTL managed by caller)
_key_cache: dict[str, tuple[str, float]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes


def get_cached_key(cache_key: str) -> str | None:
    """Get a decrypted key from cache if it hasn't expired."""
    import time
    if cache_key in _key_cache:
        value, timestamp = _key_cache[cache_key]
        if time.time() - timestamp < CACHE_TTL_SECONDS:
            return value
        else:
            del _key_cache[cache_key]
    return None


def set_cached_key(cache_key: str, value: str) -> None:
    """Cache a decrypted key."""
    import time
    _key_cache[cache_key] = (value, time.time())


def clear_cached_key(cache_key: str) -> None:
    """Remove a key from cache (call on deletion/update)."""
    _key_cache.pop(cache_key, None)