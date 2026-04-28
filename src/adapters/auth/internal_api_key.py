import hmac
from functools import lru_cache

from src.shared.config import INTERNAL_API_KEY
from src.shared.errors import ServiceUnavailableError, UnauthorizedError


def require_internal_api_key(provided_api_key: str | None) -> None:
    expected_api_key = _load_internal_api_key()
    if not isinstance(provided_api_key, str) or not provided_api_key.strip():
        raise UnauthorizedError("Missing api-key header")
    if not hmac.compare_digest(provided_api_key.strip(), expected_api_key):
        raise UnauthorizedError("Invalid api-key header")


@lru_cache(maxsize=1)
def _load_internal_api_key() -> str:
    if not isinstance(INTERNAL_API_KEY, str) or not INTERNAL_API_KEY.strip():
        raise ServiceUnavailableError("INTERNAL_API_KEY is not configured")
    return INTERNAL_API_KEY.strip()
