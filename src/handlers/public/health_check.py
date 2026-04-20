import json
import time
from datetime import datetime, timezone
from typing import Any

from botocore.exceptions import ClientError

from src.adapters.persistence.dynamodb_client import get_dynamodb_client
from src.handlers.handler_utils import cors_handler, handle_error
from src.shared.config import (
    AWS_REGION,
    DYNAMODB_TABLE_NAME,
    IDEMPOTENCY_TABLE_NAME,
    INCIDENT_CATALOG_TABLE_NAME,
    SERVICE_NAME,
    STAGE,
)
from src.shared.response import default_headers, ok

START_TIME_MONOTONIC = time.monotonic()


@cors_handler
def handler(event, context):
    try:
        probe = _resolve_probe(event)
        if probe == "live":
            return ok(_build_liveness_body(), event)

        readiness = _run_readiness_check()
        if probe == "ready":
            return _json_response(200 if readiness["status"] == "pass" else 503, readiness, event)

        summary = _build_summary_body(readiness)
        return _json_response(200 if summary["status"] == "pass" else 503, summary, event)
    except Exception as exc:
        return handle_error(exc, event)


def _resolve_probe(event: dict[str, Any] | None) -> str:
    request_context = (event or {}).get("requestContext") or {}
    http_context = request_context.get("http") or {}
    route_hint = (
        request_context.get("resourcePath")
        or (event or {}).get("resource")
        or (event or {}).get("path")
        or http_context.get("path")
        or ""
    )
    normalized = str(route_hint).rstrip("/").lower()
    if normalized.endswith("/health/live"):
        return "live"
    if normalized.endswith("/health/ready"):
        return "ready"
    return "summary"


def _build_liveness_body() -> dict[str, Any]:
    return {
        "service": SERVICE_NAME,
        "stage": STAGE,
        "region": AWS_REGION,
        "status": "pass",
        "timestamp": _utc_now_iso(),
        "checks": {
            "process": {
                "status": "pass",
                "uptimeMs": _uptime_ms(),
            }
        },
    }


def _run_readiness_check() -> dict[str, Any]:
    check_started = time.perf_counter()
    table_checks: list[dict[str, Any]] = []
    client = get_dynamodb_client()

    for label, table_name in (
        ("rescueRequestTable", DYNAMODB_TABLE_NAME),
        ("idempotencyTable", IDEMPOTENCY_TABLE_NAME),
        ("incidentCatalogTable", INCIDENT_CATALOG_TABLE_NAME),
    ):
        item_started = time.perf_counter()
        status = "fail"
        issue: str | None = None
        table_status: str | None = None

        try:
            response = client.describe_table(TableName=table_name)
            table_status = ((response.get("Table") or {}).get("TableStatus") or "").upper()
            if table_status == "ACTIVE":
                status = "pass"
            else:
                issue = f"table status is {table_status or 'UNKNOWN'}"
        except Exception as exc:
            issue = _format_exception(exc)

        table_checks.append(
            {
                "name": label,
                "tableName": table_name,
                "status": status,
                "tableStatus": table_status,
                "latencyMs": _elapsed_ms(item_started),
                "issue": issue,
            }
        )

    overall_status = "pass" if all(item["status"] == "pass" for item in table_checks) else "fail"
    return {
        "service": SERVICE_NAME,
        "stage": STAGE,
        "region": AWS_REGION,
        "status": overall_status,
        "timestamp": _utc_now_iso(),
        "checks": {
            "dynamodb": {
                "status": overall_status,
                "latencyMs": _elapsed_ms(check_started),
                "tables": table_checks,
            }
        },
    }


def _build_summary_body(readiness: dict[str, Any]) -> dict[str, Any]:
    liveness = _build_liveness_body()
    return {
        "service": SERVICE_NAME,
        "stage": STAGE,
        "region": AWS_REGION,
        "status": readiness["status"],
        "timestamp": _utc_now_iso(),
        "checks": {
            "liveness": liveness["checks"]["process"],
            "readiness": readiness["checks"]["dynamodb"],
        },
    }


def _json_response(status_code: int, body: dict[str, Any], event: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": default_headers(event),
        "body": json.dumps(body, default=str),
    }


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


def _uptime_ms() -> int:
    return max(0, int((time.monotonic() - START_TIME_MONOTONIC) * 1000))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _format_exception(exc: Exception) -> str:
    if isinstance(exc, ClientError):
        error = exc.response.get("Error") or {}
        code = error.get("Code", "ClientError")
        message = error.get("Message") or str(exc)
        return f"{code}: {message}"
    return str(exc)
