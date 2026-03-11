import json
from functools import wraps
from typing import Any

from src.shared.errors import AppError
from src.shared.logger import get_logger
from src.shared.response import (
    apply_cors_headers,
    bad_request,
    conflict,
    default_headers,
    forbidden,
    internal_error,
    not_found,
    service_unavailable,
    unprocessable_entity,
)

logger = get_logger(__name__)


def cors_handler(func):
    @wraps(func)
    def wrapper(event, context):
        response = func(event, context)
        if isinstance(response, dict) and "statusCode" in response:
            return apply_cors_headers(response, event)
        return response

    return wrapper


def parse_body(event: dict) -> dict:
    body = event.get("body")
    if not body:
        return {}
    if isinstance(body, str):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {}
    return body


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


def handle_error(e: Exception, event: dict[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(e, AppError):
        status = e.status_code
        body = {
            "message": e.message,
            "traceId": "",
            "details": e.details,
        }
        import uuid
        body["traceId"] = str(uuid.uuid4())
        return {
            "statusCode": status,
            "headers": default_headers(event),
            "body": json.dumps(body, default=str),
        }
    logger.exception("Unhandled error")
    return internal_error(event=event)
