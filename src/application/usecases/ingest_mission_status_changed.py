import json
import uuid
from datetime import datetime, timezone
from typing import Any

from src.adapters.persistence.rescue_request_repository import (
    append_event_and_update_current,
    get_current_state,
    update_current_fields,
)
from src.application.services.event_publisher import publish_resolved, publish_status_changed
from src.application.services.idempotency_service import check_and_reserve, finalize_failure, finalize_success
from src.domain.enums.request_status import RequestStatus
from src.shared.errors import NotFoundError, ValidationError
from src.shared.logger import get_logger

logger = get_logger(__name__)

CANONICAL_MESSAGE_TYPES = {
    "MissionStatusChanged",
    "MissionStatusChangedEvent",
    "mission.status.changed",
    "mission.status.changed.v1",
}
MISSION_PROGRESS_STATUSES = {"EN_ROUTE", "ON_SITE", "RESOLVED", "NEED_BACKUP"}
STATUS_MAP = {
    "EN_ROUTE": RequestStatus.IN_PROGRESS,
    "RESOLVED": RequestStatus.RESOLVED,
}


def execute(message: dict[str, Any]) -> dict[str, Any]:
    normalized_message = _normalize_message(message)
    header = normalized_message["header"]
    body = normalized_message["body"]

    errors = _validate_message(header, body)
    if errors:
        raise ValidationError("MissionStatusChanged event validation failed", errors)

    idempotency_key = (
        f"MissionStatusChangedEvent#{body['requestId']}#{body['missionId']}#{body['newStatus']}#{body['changedAt']}"
    )
    idempotency_reservation = check_and_reserve(
        idempotency_key=idempotency_key,
        operation_name="IngestMissionStatusChangedEvent",
        resource_scope=f"SQS:/mission-status-changed/{body['requestId']}",
        request_body=message,
    )
    if idempotency_reservation and idempotency_reservation.get("replay"):
        return {
            "status": "duplicate",
            "requestId": body["requestId"],
            "missionId": body["missionId"],
            "missionStatus": body["newStatus"],
        }

    try:
        result = _apply_message(header, body)
        finalize_success(
            idempotency_key=idempotency_key,
            response_status_code=200,
            response_body=json.dumps(result, default=str),
            result_resource_id=body["requestId"],
            idempotency_key_hash=idempotency_reservation.get("keyHash") if idempotency_reservation else None,
            lock_owner=idempotency_reservation.get("lockOwner") if idempotency_reservation else None,
        )
        return result
    except Exception as exc:
        finalize_failure(
            idempotency_key=idempotency_key,
            error_code="INGEST_MISSION_STATUS_CHANGED_FAILED",
            error_message=str(exc),
            idempotency_key_hash=idempotency_reservation.get("keyHash") if idempotency_reservation else None,
            lock_owner=idempotency_reservation.get("lockOwner") if idempotency_reservation else None,
        )
        raise


def _apply_message(header: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    current = get_current_state(body["requestId"])
    if not current:
        raise NotFoundError(f"Request {body['requestId']} not found")

    current_incident_id = current.get("incidentId")
    if current_incident_id and current_incident_id != body["incidentId"]:
        raise ValidationError(
            "MissionStatusChanged event incidentId does not match request current state",
            [
                {
                    "field": "body.incident_id",
                    "issue": f"expected {current_incident_id} but received {body['incidentId']}",
                }
            ],
        )

    current_status = RequestStatus(current["status"])
    if RequestStatus.is_terminal(current_status):
        return {
            "status": "skipped_terminal",
            "requestId": body["requestId"],
            "missionId": body["missionId"],
            "currentStatus": current_status.value,
            "missionStatus": body["newStatus"],
        }

    target_status = STATUS_MAP.get(body["newStatus"])
    mission_updates = _build_mission_current_updates(body)
    current_version_raw = current.get("stateVersion")
    expected_version = current_version_raw if isinstance(current_version_raw, int) else None

    if target_status is None:
        update_current_fields(
            request_id=body["requestId"],
            updates=mission_updates,
            expected_version=expected_version,
        )
        return {
            "status": "metadata_updated_unmapped_status",
            "requestId": body["requestId"],
            "missionId": body["missionId"],
            "missionStatus": body["newStatus"],
        }

    if current_status == target_status:
        update_current_fields(
            request_id=body["requestId"],
            updates=mission_updates,
            expected_version=expected_version,
        )
        return {
            "status": "metadata_updated_status_unchanged",
            "requestId": body["requestId"],
            "missionId": body["missionId"],
            "missionStatus": body["newStatus"],
            "newStatus": target_status.value,
        }

    current_version = expected_version if expected_version is not None else 0
    new_version = current_version + 1
    event_id = str(uuid.uuid4())

    current_updates = {
        **mission_updates,
        "status": target_status.value,
        "stateVersion": new_version,
        "lastEventId": event_id,
    }
    if body.get("rescueTeamId"):
        current_updates["assignedUnitId"] = body["rescueTeamId"]
        if not current.get("assignedAt"):
            current_updates["assignedAt"] = body["changedAt"]

    event_item = {
        "PK": f"REQ#{body['requestId']}",
        "SK": f"EVENT#{new_version:010d}",
        "eventId": event_id,
        "requestId": body["requestId"],
        "previousStatus": current_status.value,
        "newStatus": target_status.value,
        "changedBy": body["changedBy"],
        "changedByRole": "mission-progress-service",
        "changeReason": f"Mission status changed to {body['newStatus']}",
        "meta": _build_mission_meta(header, body),
        "priorityScore": current.get("priorityScore"),
        "responderUnitId": body.get("rescueTeamId"),
        "missionId": body["missionId"],
        "rescueTeamId": body["rescueTeamId"],
        "version": new_version,
        "occurredAt": body["changedAt"],
        "itemType": "STATUS_EVENT",
    }

    append_event_and_update_current(
        request_id=body["requestId"],
        event_item=event_item,
        current_updates=current_updates,
        expected_version=expected_version,
    )

    try:
        correlation_id = header.get("correlationId") or header.get("messageId") or body["missionId"]
        publish_status_changed(
            request_id=body["requestId"],
            previous_status=current_status.value,
            new_status=target_status.value,
            event_id=event_id,
            version=new_version,
            correlation_id=correlation_id,
        )
        if target_status == RequestStatus.RESOLVED:
            publish_resolved(request_id=body["requestId"], event_id=event_id, correlation_id=correlation_id)
    except Exception:
        logger.exception("Failed to publish status-changed after mission status ingest")

    return {
        "status": "updated",
        "requestId": body["requestId"],
        "missionId": body["missionId"],
        "missionStatus": body["newStatus"],
        "previousStatus": current_status.value,
        "newStatus": target_status.value,
        "eventId": event_id,
        "version": new_version,
    }


def _build_mission_current_updates(body: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "latestMissionId": body["missionId"],
        "latestMissionIncidentId": body["incidentId"],
        "latestMissionRescueTeamId": body["rescueTeamId"],
        "latestMissionChangedBy": body["changedBy"],
        "latestMissionStatus": body["newStatus"],
        "latestMissionStatusChangedAt": body["changedAt"],
        "lastMissionStatusIngestedAt": now,
        "lastUpdatedBy": body["changedBy"],
        "lastUpdatedAt": now,
    }


def _build_mission_meta(header: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "mission-progress-service",
        "messageId": header.get("messageId"),
        "messageType": header.get("messageType") or header.get("eventType"),
        "topicArn": header.get("topicArn"),
        "channel": header.get("channel"),
        "missionId": body["missionId"],
        "missionStatus": body["newStatus"],
        "oldMissionStatus": body.get("oldStatus"),
        "rescueTeamId": body["rescueTeamId"],
        "incidentId": body["incidentId"],
        "changedAt": body["changedAt"],
        "changedBy": body["changedBy"],
    }


def _validate_message(header: dict[str, Any], body: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []

    if not isinstance(body, dict):
        return [{"field": "body", "issue": "must be an object"}]

    if not _is_supported_message_type(header):
        errors.append({"field": "header.messageType", "issue": "must be MissionStatusChanged"})

    if not _is_version_1(body.get("schemaVersion")):
        errors.append({"field": "body.schema_version", "issue": "must equal 1.0"})

    required_fields = [
        ("requestId", "body.requestId"),
        ("incidentId", "body.incident_id"),
        ("missionId", "body.mission_id"),
        ("rescueTeamId", "body.rescue_team_id"),
        ("newStatus", "body.new_status"),
        ("changedAt", "body.changed_at"),
        ("changedBy", "body.changed_by"),
    ]
    for key, field_name in required_fields:
        if not _non_empty_text(body.get(key)):
            errors.append({"field": field_name, "issue": "is required"})

    new_status = body.get("newStatus")
    if _non_empty_text(new_status) and new_status not in MISSION_PROGRESS_STATUSES:
        errors.append(
            {
                "field": "body.new_status",
                "issue": f"must be one of: {', '.join(sorted(MISSION_PROGRESS_STATUSES))}",
            }
        )

    if body.get("changedAt") is not None and not _is_iso_datetime(body.get("changedAt")):
        errors.append({"field": "body.changed_at", "issue": "must be a valid ISO-8601 datetime"})

    return errors


def _normalize_message(message: dict[str, Any]) -> dict[str, Any]:
    raw_header = message.get("header") if isinstance(message, dict) else {}
    raw_body = message.get("body") if isinstance(message, dict) else {}
    raw_header = raw_header or {}
    raw_body = raw_body or {}

    if not isinstance(raw_body, dict):
        return {"header": raw_header, "body": raw_body}

    schema_version = _first_value(raw_body, "schema_version", "schemaVersion") or raw_header.get("version")
    return {
        "header": {
            "messageId": raw_header.get("messageId"),
            "messageType": raw_header.get("messageType") or raw_header.get("eventType"),
            "eventType": raw_header.get("eventType"),
            "correlationId": raw_header.get("correlationId"),
            "sentAt": raw_header.get("sentAt") or raw_header.get("occurredAt"),
            "version": raw_header.get("version") or raw_header.get("schemaVersion"),
            "channel": raw_header.get("channel"),
            "topicArn": raw_header.get("topicArn"),
        },
        "body": {
            "schemaVersion": schema_version,
            "missionId": _first_value(raw_body, "mission_id", "missionId", "MissionID"),
            "requestId": _first_value(raw_body, "requestId", "request_id", "RequestID"),
            "incidentId": _first_value(raw_body, "incident_id", "incidentId", "IncidentID"),
            "rescueTeamId": _first_value(raw_body, "rescue_team_id", "rescueTeamId", "RescueTeamID"),
            "oldStatus": _first_value(raw_body, "old_status", "oldStatus", "OldStatus"),
            "newStatus": _first_value(raw_body, "new_status", "newStatus", "NewStatus"),
            "changedAt": _first_value(raw_body, "changed_at", "changedAt", "ChangedAt"),
            "changedBy": _first_value(raw_body, "changed_by", "changedBy", "ChangedBy"),
        },
    }


def _first_value(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return None


def _is_supported_message_type(header: dict[str, Any]) -> bool:
    message_type = header.get("messageType") or header.get("eventType")
    if message_type is None:
        return True
    return isinstance(message_type, str) and message_type in CANONICAL_MESSAGE_TYPES


def _is_version_1(value: Any) -> bool:
    if value is None:
        return False
    normalized = str(value).strip()
    return normalized in {"1", "1.0"}


def _is_iso_datetime(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
