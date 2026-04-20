import json
import hashlib
import os
import time
import uuid
from functools import wraps
from typing import Any

from src.shared.errors import AppError, BadRequestError
from src.shared.logger import get_logger
from src.shared.response import (
    apply_cors_headers,
    error_response,
    internal_error,
)
from src.shared.validators import validate_uuid

logger = get_logger(__name__)
MAX_LOGGED_BODY_BYTES = 1024 * 64
MAX_LOGGED_BODY_PREVIEW_CHARS = 2000
LOG_PAYLOAD_PREVIEW = os.environ.get("LOG_PAYLOAD_PREVIEW", "false").strip().lower() in {"1", "true", "yes"}


def cors_handler(func):
    @wraps(func)
    def wrapper(event, context):
        started = time.perf_counter()
        _log_api_request(event, context, func.__name__)
        response: Any = None
        raised_error: Exception | None = None

        try:
            response = func(event, context)
            if isinstance(response, dict) and "statusCode" in response:
                response = apply_cors_headers(response, event)
            return response
        except Exception as exc:
            raised_error = exc
            raise
        finally:
            _log_api_response(
                event=event,
                context=context,
                handler_name=func.__name__,
                response=response,
                started_at=started,
                raised_error=raised_error,
            )

    return wrapper


def parse_body(event: dict) -> dict:
    body = event.get("body")
    if body is None or body == "":
        return {}
    if isinstance(body, str):
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            raise BadRequestError(
                "Request body must be valid JSON",
                [{"field": "body", "issue": "must be valid JSON"}],
            )
    else:
        parsed = body

    if not isinstance(parsed, dict):
        raise BadRequestError(
            "Request body must be a JSON object",
            [{"field": "body", "issue": "must be a JSON object"}],
        )

    return parsed


def get_path_param(event: dict, name: str) -> str | None:
    params = event.get("pathParameters") or {}
    return params.get(name)


def get_query_param(event: dict, name: str, default: str | None = None) -> str | None:
    params = event.get("queryStringParameters") or {}
    return params.get(name, default)


def get_header(event: dict, name: str, default: str | None = None) -> str | None:
    headers = event.get("headers") or {}
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return default


def require_path_param(event: dict, name: str) -> str:
    value = get_path_param(event, name)
    if not isinstance(value, str) or not value.strip():
        raise BadRequestError(
            f"Missing required path parameter: {name}",
            [{"field": name, "issue": "path parameter is required"}],
        )
    return value.strip()


def require_uuid_path_param(event: dict, name: str) -> str:
    value = require_path_param(event, name)
    return validate_uuid(value, field_name=name)


def handle_error(e: Exception, event: dict[str, Any] | None = None) -> dict[str, Any]:
    trace_id = str(uuid.uuid4())
    if isinstance(e, AppError):
        logger.warning(
            "Handled application error",
            extra={
                "extra_data": {
                    "traceId": trace_id,
                    "statusCode": e.status_code,
                    "errorCode": e.error_code,
                    "path": (event or {}).get("path"),
                    "httpMethod": (event or {}).get("httpMethod"),
                }
            },
        )
        return error_response(
            status_code=e.status_code,
            message=e.message,
            error_code=e.error_code,
            details=e.details,
            event=event,
            trace_id=trace_id,
        )
    logger.exception(
        "Unhandled error",
        extra={
            "extra_data": {
                "traceId": trace_id,
                "path": (event or {}).get("path"),
                "httpMethod": (event or {}).get("httpMethod"),
            }
        },
    )
    return internal_error(event=event, trace_id=trace_id)


def _log_api_request(event: dict[str, Any] | None, context: Any, handler_name: str) -> None:
    request_context = (event or {}).get("requestContext") or {}
    http_context = request_context.get("http") or {}
    headers = (event or {}).get("headers") or {}

    logger.info(
        "API handler invoked",
        extra={
            "extra_data": {
                "handler": handler_name,
                "awsRequestId": getattr(context, "aws_request_id", None),
                "apiRequestId": request_context.get("requestId"),
                "httpMethod": (event or {}).get("httpMethod") or http_context.get("method"),
                "path": (
                    (event or {}).get("path")
                    or (event or {}).get("resource")
                    or http_context.get("path")
                    or request_context.get("resourcePath")
                ),
                "routeKey": request_context.get("routeKey"),
                "pathParameters": (event or {}).get("pathParameters") or {},
                "queryStringParameters": (event or {}).get("queryStringParameters") or {},
                "selectedHeaders": _extract_selected_headers(headers),
                "body": _summarize_body((event or {}).get("body")),
            }
        },
    )


def _log_api_response(
    event: dict[str, Any] | None,
    context: Any,
    handler_name: str,
    response: Any,
    started_at: float,
    raised_error: Exception | None,
) -> None:
    response_body = response.get("body") if isinstance(response, dict) else None
    logger.info(
        "API handler completed",
        extra={
            "extra_data": {
                "handler": handler_name,
                "awsRequestId": getattr(context, "aws_request_id", None),
                "apiRequestId": ((event or {}).get("requestContext") or {}).get("requestId"),
                "statusCode": response.get("statusCode") if isinstance(response, dict) else None,
                "durationMs": int((time.perf_counter() - started_at) * 1000),
                "responseBodyBytes": _string_size_bytes(response_body),
                "raisedError": type(raised_error).__name__ if raised_error else None,
            }
        },
    )


def _extract_selected_headers(headers: dict[str, Any]) -> dict[str, Any]:
    content_type = _lookup_header(headers, "content-type")
    user_agent = _lookup_header(headers, "user-agent")
    forwarded_for = _lookup_header(headers, "x-forwarded-for")
    if_match = _lookup_header(headers, "if-match")
    idempotency_key = _lookup_header(headers, "x-idempotency-key")

    selected = {
        "content-type": content_type,
        "user-agent": user_agent,
        "x-forwarded-for": forwarded_for,
        "if-match": if_match,
    }
    if idempotency_key:
        selected["x-idempotency-key-hash"] = _sha256_text(idempotency_key)
    return selected


def _lookup_header(headers: dict[str, Any], key: str) -> str | None:
    for header_name, header_value in headers.items():
        if header_name.lower() == key:
            return header_value
    return None


def _summarize_body(body: Any) -> dict[str, Any]:
    if body is None or body == "":
        return {"present": False}

    if isinstance(body, str):
        raw = body
        summary = {
            "present": True,
            "kind": "string",
            "sizeBytes": _string_size_bytes(raw),
            "sha256": _sha256_text(raw),
        }
        if summary["sizeBytes"] <= MAX_LOGGED_BODY_BYTES:
            try:
                parsed = json.loads(raw)
                summary["jsonType"] = type(parsed).__name__
                if isinstance(parsed, dict):
                    summary["keys"] = sorted(parsed.keys())
            except json.JSONDecodeError:
                summary["jsonType"] = "invalid"
            if LOG_PAYLOAD_PREVIEW:
                summary["preview"] = raw[:MAX_LOGGED_BODY_PREVIEW_CHARS]
        else:
            summary["jsonType"] = "skipped_large_payload"
        return summary

    if isinstance(body, dict):
        serialized = json.dumps(body, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
        summary = {
            "present": True,
            "kind": "object",
            "sizeBytes": _string_size_bytes(serialized),
            "sha256": _sha256_text(serialized),
            "keys": sorted(body.keys()),
        }
        if LOG_PAYLOAD_PREVIEW:
            summary["preview"] = serialized[:MAX_LOGGED_BODY_PREVIEW_CHARS]
        return summary

    if isinstance(body, list):
        serialized = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        summary = {
            "present": True,
            "kind": "array",
            "sizeBytes": _string_size_bytes(serialized),
            "sha256": _sha256_text(serialized),
            "itemCount": len(body),
        }
        if LOG_PAYLOAD_PREVIEW:
            summary["preview"] = serialized[:MAX_LOGGED_BODY_PREVIEW_CHARS]
        return summary

    serialized = str(body)
    summary = {
        "present": True,
        "kind": type(body).__name__,
        "sizeBytes": _string_size_bytes(serialized),
        "sha256": _sha256_text(serialized),
    }
    if LOG_PAYLOAD_PREVIEW:
        summary["preview"] = serialized[:MAX_LOGGED_BODY_PREVIEW_CHARS]
    return summary


def _sha256_text(value: Any) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _string_size_bytes(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        return len(value.encode("utf-8"))
    return len(str(value).encode("utf-8"))
