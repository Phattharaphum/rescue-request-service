import hmac
import json
from functools import lru_cache
from typing import Any

import boto3

from src.shared.config import AWS_ENDPOINT_URL, AWS_REGION, INTERNAL_API_KEY_SECRET_ID, STAGE
from src.shared.errors import ServiceUnavailableError, UnauthorizedError


def require_internal_api_key(provided_api_key: str | None) -> None:
    expected_api_key = _load_internal_api_key()
    if not isinstance(provided_api_key, str) or not provided_api_key.strip():
        raise UnauthorizedError("Missing api-key header")
    if not hmac.compare_digest(provided_api_key.strip(), expected_api_key):
        raise UnauthorizedError("Invalid api-key header")


def _get_secrets_manager_client():
    kwargs = {"region_name": AWS_REGION}
    if STAGE == "local" and AWS_ENDPOINT_URL:
        kwargs["endpoint_url"] = AWS_ENDPOINT_URL
    return boto3.client("secretsmanager", **kwargs)


@lru_cache(maxsize=1)
def _load_internal_api_key() -> str:
    if not INTERNAL_API_KEY_SECRET_ID:
        raise ServiceUnavailableError("INTERNAL_API_KEY_SECRET_ID is not configured")

    response = _get_secrets_manager_client().get_secret_value(SecretId=INTERNAL_API_KEY_SECRET_ID)
    secret_string = response.get("SecretString", "")
    api_key = _extract_api_key(secret_string)
    if not api_key:
        raise ServiceUnavailableError("Internal api-key secret is empty or missing apiKey")
    return api_key


def _extract_api_key(secret_string: str) -> str | None:
    if not isinstance(secret_string, str) or not secret_string.strip():
        return None

    text = secret_string.strip()
    try:
        parsed: Any = json.loads(text)
    except json.JSONDecodeError:
        return text

    if isinstance(parsed, str):
        return parsed.strip() or None
    if not isinstance(parsed, dict):
        return None

    for key in ("apiKey", "api-key", "key", "value"):
        value = parsed.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
