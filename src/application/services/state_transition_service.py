import uuid
from datetime import datetime, timezone
from typing import Any

from src.adapters.persistence.rescue_request_repository import (
    append_event_and_update_current,
    get_current_state,
)
from src.domain.enums.request_status import RequestStatus
from src.domain.rules.transition_rules import validate_transition, validate_transition_requirements
from src.shared.errors import ConflictError, NotFoundError
from src.shared.logger import get_logger

logger = get_logger(__name__)


def execute_transition(
    request_id: str,
    new_status: RequestStatus,
    changed_by: str,
    changed_by_role: str,
    payload: dict[str, Any] | None = None,
    expected_version: int | None = None,
) -> dict[str, Any]:
    payload = payload or {}

    current = get_current_state(request_id)
    if not current:
        raise NotFoundError(f"Request {request_id} not found")

    current_status = RequestStatus(current["status"])
    current_version = current.get("stateVersion", 0)

    if expected_version is not None and expected_version != current_version:
        raise ConflictError(
            "Version mismatch",
            [{"field": "If-Match", "issue": f"expected {expected_version} but current is {current_version}"}],
        )

    validate_transition(current_status, new_status)
    validate_transition_requirements(new_status, payload)

    new_version = current_version + 1
    event_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    event_item = {
        "PK": f"REQ#{request_id}",
        "SK": f"EVENT#{new_version:010d}",
        "eventId": event_id,
        "requestId": request_id,
        "previousStatus": current_status.value,
        "newStatus": new_status.value,
        "changedBy": changed_by,
        "changedByRole": changed_by_role,
        "changeReason": payload.get("reason"),
        "meta": payload.get("meta"),
        "priorityScore": payload.get("priorityScore"),
        "responderUnitId": payload.get("responderUnitId"),
        "version": new_version,
        "occurredAt": now,
        "itemType": "STATUS_EVENT",
    }

    current_updates = {
        "status": new_status.value,
        "stateVersion": new_version,
        "lastEventId": event_id,
        "lastUpdatedBy": changed_by,
        "lastUpdatedAt": now,
    }

    if payload.get("priorityScore") is not None:
        current_updates["priorityScore"] = payload["priorityScore"]
    if payload.get("priorityLevel"):
        current_updates["priorityLevel"] = payload["priorityLevel"]
    if payload.get("responderUnitId"):
        current_updates["assignedUnitId"] = payload["responderUnitId"]
        current_updates["assignedAt"] = now
    if payload.get("note"):
        current_updates["latestNote"] = payload["note"]

    append_event_and_update_current(
        request_id=request_id,
        event_item=event_item,
        current_updates=current_updates,
        expected_version=current_version,
    )

    return {
        "eventId": event_id,
        "requestId": request_id,
        "previousStatus": current_status.value,
        "newStatus": new_status.value,
        "version": new_version,
        "occurredAt": now,
    }
