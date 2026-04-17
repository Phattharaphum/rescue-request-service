import json
import math
import uuid
from datetime import datetime, timezone
from typing import Any

from src.adapters.persistence.rescue_request_repository import get_current_state, update_current_fields
from src.application.services.idempotency_service import check_and_reserve, finalize_failure, finalize_success
from src.domain.enums.request_status import RequestStatus
from src.shared.errors import NotFoundError, ValidationError
from src.shared.logger import get_logger

logger = get_logger(__name__)

ALLOWED_PRIORITY_LEVELS = {"LOW", "NORMAL", "HIGH", "CRITICAL"}


def execute(message: dict[str, Any]) -> dict[str, Any]:
    header = message.get("header") or {}
    body = message.get("body") or {}

    errors = _validate_message(header, body)
    if errors:
        raise ValidationError("RescueRequestEvaluatedEvent validation failed", errors)

    idempotency_key = f"RescueRequestEvaluatedEvent#{body['evaluateId']}"
    replay = check_and_reserve(
        idempotency_key=idempotency_key,
        operation_name="IngestRescueRequestEvaluatedEvent",
        request_body=message,
    )
    if replay and replay.get("replay"):
        return {
            "status": "duplicate",
            "requestId": body["requestId"],
            "evaluateId": body["evaluateId"],
        }

    try:
        current = get_current_state(body["requestId"])
        if not current:
            raise NotFoundError(f"Request {body['requestId']} not found")

        expected_correlation = current.get("lastPrioritizationMessageId")
        actual_correlation = header.get("correlationId")
        if expected_correlation and actual_correlation and expected_correlation != actual_correlation:
            raise ValidationError(
                "RescueRequestEvaluatedEvent correlationId does not match the latest prioritization message",
                [{
                    "field": "header.correlationId",
                    "issue": f"expected {expected_correlation} but received {actual_correlation}",
                }],
            )

        current_status = RequestStatus(current["status"])
        if RequestStatus.is_terminal(current_status):
            result = {
                "status": "skipped_terminal",
                "requestId": body["requestId"],
                "evaluateId": body["evaluateId"],
            }
            finalize_success(
                idempotency_key=idempotency_key,
                response_status_code=200,
                response_body=json.dumps(result, default=str),
                result_resource_id=body["requestId"],
            )
            return result

        now = datetime.now(timezone.utc).isoformat()
        updates = {
            "priorityScore": _normalize_priority_score(body["priorityScore"]),
            "priorityLevel": body["priorityLevel"],
            "latestPriorityEvaluationId": body["evaluateId"],
            "latestPriorityReason": body["evaluateReason"],
            "latestPriorityEvaluatedAt": body["lastEvaluatedAt"],
            "latestPriorityCorrelationId": actual_correlation,
            "lastPriorityIngestedAt": now,
            "lastUpdatedAt": now,
            "lastUpdatedBy": "prioritization-service",
        }
        update_current_fields(request_id=body["requestId"], updates=updates)

        result = {
            "status": "updated",
            "requestId": body["requestId"],
            "evaluateId": body["evaluateId"],
            "priorityScore": updates["priorityScore"],
            "priorityLevel": updates["priorityLevel"],
        }
        finalize_success(
            idempotency_key=idempotency_key,
            response_status_code=200,
            response_body=json.dumps(result, default=str),
            result_resource_id=body["requestId"],
        )
        return result
    except Exception as exc:
        finalize_failure(idempotency_key=idempotency_key, error_code="INGEST_EVALUATION_FAILED", error_message=str(exc))
        raise


def _validate_message(header: dict[str, Any], body: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []

    if header.get("messageType") != "RescueRequestEvaluatedEvent":
        errors.append({"field": "header.messageType", "issue": "must be RescueRequestEvaluatedEvent"})

    if not _is_iso_datetime(header.get("sentAt")):
        errors.append({"field": "header.sentAt", "issue": "must be a valid ISO-8601 datetime"})

    if str(header.get("version")) != "1":
        errors.append({"field": "header.version", "issue": "must equal 1"})

    if not _non_empty_text(body.get("requestId")):
        errors.append({"field": "body.requestId", "issue": "is required"})

    if not _is_uuid(body.get("incidentId")):
        errors.append({"field": "body.incidentId", "issue": "must be a valid UUID"})

    if not _is_uuid(body.get("evaluateId")):
        errors.append({"field": "body.evaluateId", "issue": "must be a valid UUID"})

    priority_score = body.get("priorityScore")
    if isinstance(priority_score, bool) or not isinstance(priority_score, (int, float)):
        errors.append({"field": "body.priorityScore", "issue": "must be a number between 0 and 1"})
    elif not math.isfinite(float(priority_score)) or float(priority_score) < 0 or float(priority_score) > 1:
        errors.append({"field": "body.priorityScore", "issue": "must be a number between 0 and 1"})

    if body.get("priorityLevel") not in ALLOWED_PRIORITY_LEVELS:
        errors.append({
            "field": "body.priorityLevel",
            "issue": f"must be one of: {', '.join(sorted(ALLOWED_PRIORITY_LEVELS))}",
        })

    if not _non_empty_text(body.get("evaluateReason")):
        errors.append({"field": "body.evaluateReason", "issue": "is required"})

    if not _is_iso_datetime(body.get("lastEvaluatedAt")):
        errors.append({"field": "body.lastEvaluatedAt", "issue": "must be a valid ISO-8601 datetime"})

    submitted_at = body.get("submittedAt")
    if submitted_at is not None and not _is_iso_datetime(submitted_at):
        errors.append({"field": "body.submittedAt", "issue": "must be a valid ISO-8601 datetime"})

    location = body.get("location")
    if not isinstance(location, dict):
        errors.append({"field": "body.location", "issue": "is required"})
    else:
        if not _is_number(location.get("latitude")):
            errors.append({"field": "body.location.latitude", "issue": "must be a valid number"})
        if not _is_number(location.get("longitude")):
            errors.append({"field": "body.location.longitude", "issue": "must be a valid number"})

    return errors


def _normalize_priority_score(value: Any) -> float | int:
    if isinstance(value, int):
        return value
    return float(value)


def _is_uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


def _is_iso_datetime(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _is_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(parsed)


def _non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
