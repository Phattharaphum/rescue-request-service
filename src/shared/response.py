import json
import uuid
from typing import Any


def _build_response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "X-Trace-Id": str(uuid.uuid4()),
        },
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


def ok(body: dict[str, Any]) -> dict[str, Any]:
    return _build_response(200, body)


def created(body: dict[str, Any]) -> dict[str, Any]:
    return _build_response(201, body)


def bad_request(message: str, details: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return _build_response(400, _error_body(message, details))


def unauthorized(message: str = "Unauthorized") -> dict[str, Any]:
    return _build_response(401, _error_body(message))


def forbidden(message: str = "Forbidden") -> dict[str, Any]:
    return _build_response(403, _error_body(message))


def not_found(message: str = "Resource not found") -> dict[str, Any]:
    return _build_response(404, _error_body(message))


def conflict(message: str, details: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return _build_response(409, _error_body(message, details))


def unprocessable_entity(message: str, details: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return _build_response(422, _error_body(message, details))


def service_unavailable(message: str = "Service temporarily unavailable") -> dict[str, Any]:
    return _build_response(503, _error_body(message))


def internal_error(message: str = "Internal server error") -> dict[str, Any]:
    return _build_response(500, _error_body(message))
