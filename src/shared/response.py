import json
import os
import uuid
from datetime import datetime, timezone
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


def _resolve_request_metadata(event: dict[str, Any] | None = None) -> dict[str, str | None]:
    if not event:
        return {
            "requestId": None,
            "path": None,
            "method": None,
        }

    request_context = event.get("requestContext") or {}
    http_context = request_context.get("http") or {}

    return {
        "requestId": request_context.get("requestId"),
        "path": event.get("path") or request_context.get("path") or http_context.get("path"),
        "method": event.get("httpMethod") or http_context.get("method"),
    }


def default_headers(event: dict[str, Any] | None = None, trace_id: str | None = None) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "X-Trace-Id": trace_id or str(uuid.uuid4()),
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


def _build_response(
    status_code: int,
    body: dict[str, Any],
    event: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    resolved_trace_id = trace_id or str(uuid.uuid4())
    return {
        "statusCode": status_code,
        "headers": default_headers(event, trace_id=resolved_trace_id),
        "body": json.dumps(body, default=str),
    }


def _error_body(
    message: str,
    error_code: str,
    details: list[dict[str, Any]] | None = None,
    event: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    resolved_trace_id = trace_id or str(uuid.uuid4())
    metadata = _resolve_request_metadata(event)
    body: dict[str, Any] = {
        "message": message,
        "errorCode": error_code,
        "traceId": resolved_trace_id,
        "requestId": metadata["requestId"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "path": metadata["path"],
        "method": metadata["method"],
        "details": details or [],
    }
    return body


def error_response(
    status_code: int,
    message: str,
    error_code: str,
    details: list[dict[str, Any]] | None = None,
    event: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    resolved_trace_id = trace_id or str(uuid.uuid4())
    return _build_response(
        status_code,
        _error_body(
            message=message,
            error_code=error_code,
            details=details,
            event=event,
            trace_id=resolved_trace_id,
        ),
        event=event,
        trace_id=resolved_trace_id,
    )


def ok(body: dict[str, Any], event: dict[str, Any] | None = None) -> dict[str, Any]:
    return _build_response(200, body, event)


def created(body: dict[str, Any], event: dict[str, Any] | None = None) -> dict[str, Any]:
    return _build_response(201, body, event)


def bad_request(message: str, details: list[dict[str, Any]] | None = None, event: dict[str, Any] | None = None) -> dict[str, Any]:
    return error_response(400, message, "BAD_REQUEST", details=details, event=event)


def unauthorized(message: str = "Unauthorized", event: dict[str, Any] | None = None) -> dict[str, Any]:
    return error_response(401, message, "UNAUTHORIZED", event=event)


def forbidden(message: str = "Forbidden", event: dict[str, Any] | None = None) -> dict[str, Any]:
    return error_response(403, message, "FORBIDDEN", event=event)


def not_found(
    message: str = "Resource not found",
    details: list[dict[str, Any]] | None = None,
    event: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return error_response(404, message, "NOT_FOUND", details=details, event=event)


def conflict(message: str, details: list[dict[str, Any]] | None = None, event: dict[str, Any] | None = None) -> dict[str, Any]:
    return error_response(409, message, "CONFLICT", details=details, event=event)


def unprocessable_entity(message: str, details: list[dict[str, Any]] | None = None, event: dict[str, Any] | None = None) -> dict[str, Any]:
    return error_response(422, message, "VALIDATION_ERROR", details=details, event=event)


def service_unavailable(message: str = "Service temporarily unavailable", event: dict[str, Any] | None = None) -> dict[str, Any]:
    return error_response(503, message, "SERVICE_UNAVAILABLE", event=event)


def internal_error(
    message: str = "Internal server error",
    event: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    return error_response(500, message, "INTERNAL_ERROR", event=event, trace_id=trace_id)
