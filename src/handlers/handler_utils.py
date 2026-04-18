import json
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
