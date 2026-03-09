from typing import Any

from src.shared.logger import get_logger

logger = get_logger(__name__)


def parse_auth_context(event: dict[str, Any]) -> dict[str, Any]:
    headers = event.get("headers") or {}
    return {
        "userId": headers.get("X-User-Id", "anonymous"),
        "role": headers.get("X-User-Role", "citizen"),
        "authenticated": False,
    }


def extract_citizen_auth(event: dict[str, Any]) -> dict[str, Any]:
    headers = event.get("headers") or {}
    return {
        "phoneHash": headers.get("X-Phone-Hash", ""),
        "trackingCodeHash": headers.get("X-Tracking-Code-Hash", ""),
        "authMethod": "tracking_code",
    }
