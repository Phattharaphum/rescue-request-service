import json
import os
import uuid
from typing import Any

DEFAULT_ALLOWED_ORIGINS = [
    "https://rescue-request.phatphum.me",
    "http://localhost:3000",
]
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", ",".join(DEFAULT_ALLOWED_ORIGINS)).split(",")
    if origin.strip()
]
ALLOWED_ORIGIN = ALLOWED_ORIGINS[0]


def resolve_allowed_origin(event: dict[str, Any] | None = None) -> str:
    if event:
        headers = event.get("headers") or {}
        origin = headers.get("origin") or headers.get("Origin")
        if isinstance(origin, str) and origin in ALLOWED_ORIGINS:
            return origin
    return ALLOWED_ORIGIN


def default_headers(event: dict[str, Any] | None = None) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "X-Trace-Id": str(uuid.uuid4()),
        "Vary": "Origin",
    }
    origin = resolve_allowed_origin(event)
    if origin:
        headers["Access-Control-Allow-Origin"] = origin
    return headers


def apply_cors_headers(response: dict[str, Any], event: dict[str, Any] | None = None) -> dict[str, Any]:
    headers = dict(response.get("headers") or {})
    headers["Vary"] = "Origin"
    origin = resolve_allowed_origin(event)
    if origin:
        headers["Access-Control-Allow-Origin"] = origin
    response["headers"] = headers
    return response


def _build_response(status_code: int, body: dict[str, Any], event: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": default_headers(event),
        "body": json.dumps(body, default=str),
    }


def _error_body(message: str, details: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "message": message,
        "traceId": str(uuid.uuid4()),
    }
    if details:
        body["details"] = details
    return body


def ok(body: dict[str, Any], event: dict[str, Any] | None = None) -> dict[str, Any]:
    return _build_response(200, body, event)


def created(body: dict[str, Any], event: dict[str, Any] | None = None) -> dict[str, Any]:
    return _build_response(201, body, event)


def bad_request(message: str, details: list[dict[str, Any]] | None = None, event: dict[str, Any] | None = None) -> dict[str, Any]:
    return _build_response(400, _error_body(message, details), event)


def unauthorized(message: str = "Unauthorized", event: dict[str, Any] | None = None) -> dict[str, Any]:
    return _build_response(401, _error_body(message), event)


def forbidden(message: str = "Forbidden", event: dict[str, Any] | None = None) -> dict[str, Any]:
    return _build_response(403, _error_body(message), event)


def not_found(message: str = "Resource not found", event: dict[str, Any] | None = None) -> dict[str, Any]:
    return _build_response(404, _error_body(message), event)


def conflict(message: str, details: list[dict[str, Any]] | None = None, event: dict[str, Any] | None = None) -> dict[str, Any]:
    return _build_response(409, _error_body(message, details), event)


def unprocessable_entity(message: str, details: list[dict[str, Any]] | None = None, event: dict[str, Any] | None = None) -> dict[str, Any]:
    return _build_response(422, _error_body(message, details), event)


def service_unavailable(message: str = "Service temporarily unavailable", event: dict[str, Any] | None = None) -> dict[str, Any]:
    return _build_response(503, _error_body(message), event)


def internal_error(message: str = "Internal server error", event: dict[str, Any] | None = None) -> dict[str, Any]:
    return _build_response(500, _error_body(message), event)
