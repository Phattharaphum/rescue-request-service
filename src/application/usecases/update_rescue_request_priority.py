import json
import math
from datetime import datetime, timezone
from typing import Any

from botocore.exceptions import ClientError

from src.adapters.persistence.rescue_request_repository import get_current_state, update_current_fields
from src.application.services.event_publisher import publish_priority_score_updated
from src.application.services.idempotency_service import check_and_reserve, finalize_failure, finalize_success
from src.domain.enums.request_status import RequestStatus
from src.shared.errors import ConflictError, NotFoundError, ValidationError
from src.shared.logger import get_logger

logger = get_logger(__name__)

ALLOWED_FIELDS = {"priorityScore", "priorityLevel", "note"}


def execute(
    request_id: str,
    body: dict,
    idempotency_key: str | None = None,
    expected_version: int | None = None,
) -> dict:
    idempotency_reservation: dict | None = None
    unsupported_fields = sorted(set(body.keys()) - ALLOWED_FIELDS)
    if unsupported_fields:
        raise ValidationError(
            "Input validation failed",
            [{"field": field, "issue": "field is not supported"} for field in unsupported_fields],
        )

    if not any(field in body for field in ALLOWED_FIELDS):
        raise ValidationError(
            "Input validation failed",
            [{"field": "body", "issue": "at least one of priorityScore, priorityLevel, note is required"}],
        )

    validation_errors = _validate_body(body)
    if validation_errors:
        raise ValidationError("Input validation failed", validation_errors)

    if idempotency_key:
        idempotency_reservation = check_and_reserve(
            idempotency_key=idempotency_key,
            operation_name="UpdateRescueRequestPriority",
            resource_scope=f"PATCH:/v1/rescue-requests/{request_id}/priority",
            request_body=body,
        )
        if idempotency_reservation and idempotency_reservation.get("replay"):
            return json.loads(idempotency_reservation["body"])

    current = get_current_state(request_id)
    if not current:
        raise NotFoundError(f"Request {request_id} not found")

    current_status = RequestStatus(current["status"])
    if RequestStatus.is_terminal(current_status):
        raise ConflictError("Cannot modify priority for a request in terminal state")

    current_version = current.get("stateVersion", 0)
    if expected_version is not None and expected_version != current_version:
        raise ConflictError(
            "Version mismatch",
            [{"field": "If-Match", "issue": f"expected {expected_version} but current is {current_version}"}],
        )

    now = datetime.now(timezone.utc).isoformat()
    updated_fields: list[str] = []
    updates: dict[str, Any] = {"lastUpdatedAt": now}

    resolved_priority_score = current.get("priorityScore")
    resolved_priority_level = current.get("priorityLevel")
    resolved_note = current.get("latestNote")

    if "priorityScore" in body:
        resolved_priority_score = _normalize_priority_score(body.get("priorityScore"))
        updates["priorityScore"] = resolved_priority_score
        updated_fields.append("priorityScore")

    if "priorityLevel" in body:
        resolved_priority_level = _normalize_nullable_text(body.get("priorityLevel"))
        updates["priorityLevel"] = resolved_priority_level
        updated_fields.append("priorityLevel")

    if "note" in body:
        resolved_note = _normalize_nullable_text(body.get("note"))
        updates["latestNote"] = resolved_note
        updated_fields.append("note")

    try:
        update_current_fields(
            request_id=request_id,
            updates=updates,
            expected_version=current_version if expected_version is not None else None,
        )
    except ClientError as e:
        if idempotency_key:
            finalize_failure(
                idempotency_key=idempotency_key,
                error_code="UPDATE_PRIORITY_FAILED",
                error_message=str(e),
                idempotency_key_hash=idempotency_reservation.get("keyHash") if idempotency_reservation else None,
                lock_owner=idempotency_reservation.get("lockOwner") if idempotency_reservation else None,
            )
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ConditionalCheckFailedException":
            if expected_version is not None:
                raise ConflictError(
                    "Version mismatch",
                    [{"field": "If-Match", "issue": "stateVersion no longer matches current value"}],
                )
            raise NotFoundError(f"Request {request_id} not found")
        raise
    except Exception as e:
        if idempotency_key:
            finalize_failure(
                idempotency_key=idempotency_key,
                error_code="UPDATE_PRIORITY_FAILED",
                error_message=str(e),
                idempotency_key_hash=idempotency_reservation.get("keyHash") if idempotency_reservation else None,
                lock_owner=idempotency_reservation.get("lockOwner") if idempotency_reservation else None,
            )
        raise

    result = {
        "requestId": request_id,
        "priorityScore": resolved_priority_score,
        "priorityLevel": resolved_priority_level,
        "note": resolved_note,
        "updatedAt": now,
        "updated": updated_fields,
    }

    if idempotency_key:
        finalize_success(
            idempotency_key=idempotency_key,
            response_status_code=200,
            response_body=json.dumps(result, default=str),
            idempotency_key_hash=idempotency_reservation.get("keyHash") if idempotency_reservation else None,
            lock_owner=idempotency_reservation.get("lockOwner") if idempotency_reservation else None,
        )

    if "priorityScore" in body and resolved_priority_score != current.get("priorityScore"):
        try:
            publish_priority_score_updated(
                request_id=request_id,
                previous_priority_score=current.get("priorityScore"),
                new_priority_score=resolved_priority_score,
                priority_level=resolved_priority_level,
                note=resolved_note,
                updated_at=now,
                correlation_id=request_id,
            )
        except Exception:
            logger.exception("Failed to publish priority-score-updated event")

    return result


def _validate_body(body: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []

    if "priorityScore" in body:
        priority_score = body.get("priorityScore")
        if priority_score is not None:
            if isinstance(priority_score, bool) or not isinstance(priority_score, (int, float)):
                errors.append({"field": "priorityScore", "issue": "must be a number or null"})
            elif not math.isfinite(float(priority_score)):
                errors.append({"field": "priorityScore", "issue": "must be a finite number"})
            elif float(priority_score) < 0 or float(priority_score) > 1:
                errors.append({"field": "priorityScore", "issue": "must be between 0 and 1"})

    if "priorityLevel" in body and not _is_nullable_non_empty_text(body.get("priorityLevel")):
        errors.append({"field": "priorityLevel", "issue": "must be a non-empty string or null"})

    if "note" in body and not _is_nullable_non_empty_text(body.get("note")):
        errors.append({"field": "note", "issue": "must be a non-empty string or null"})

    return errors


def _is_nullable_non_empty_text(value: Any) -> bool:
    return value is None or (isinstance(value, str) and bool(value.strip()))


def _normalize_priority_score(value: Any) -> float | int | None:
    if value is None:
        return None
    # Keep integer values as-is to avoid unnecessary representation changes.
    if isinstance(value, int):
        return value
    return float(value)


def _normalize_nullable_text(value: Any) -> str | None:
    if value is None:
        return None
    return value.strip()
