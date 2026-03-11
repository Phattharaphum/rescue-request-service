import json
import uuid
from datetime import datetime, timezone
from typing import Any

from src.adapters.persistence.rescue_request_repository import (
    get_master,
    get_current_state,
    put_citizen_update,
    update_master_fields,
)
from src.adapters.utils.hashing import hash_tracking_code
from src.application.services.event_publisher import publish_citizen_updated
from src.application.services.idempotency_service import check_and_reserve, finalize_failure, finalize_success
from src.domain.enums.update_type import UpdateType
from src.domain.enums.request_status import RequestStatus
from src.shared.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from src.shared.logger import get_logger
from src.shared.validators import validate_phone, validate_required_fields

logger = get_logger(__name__)


def execute(
    request_id: str,
    body: dict,
    idempotency_key: str | None = None,
    client_ip: str | None = None,
    user_agent: str | None = None,
    citizen_phone_hash: str | None = None,
    tracking_code_hash: str | None = None,
) -> dict:
    errors = validate_required_fields(body, ["updateType", "updatePayload", "trackingCode"])
    if errors:
        raise ValidationError("Input validation failed", errors)

    try:
        update_type = UpdateType(body["updateType"])
    except ValueError:
        raise ValidationError(
            f"Invalid updateType: {body['updateType']}",
            [{"field": "updateType", "issue": f"must be one of: {', '.join(t.value for t in UpdateType)}"}],
        )

    payload_errors = _validate_update_payload(update_type, body.get("updatePayload"))
    if payload_errors:
        raise ValidationError("Input validation failed", payload_errors)

    if idempotency_key:
        replay = check_and_reserve(
            idempotency_key=idempotency_key,
            operation_name="CreateCitizenUpdate",
            request_body=body,
            request_ip=client_ip,
            user_agent=user_agent,
        )
        if replay and replay.get("replay"):
            return json.loads(replay["body"])

    current = get_current_state(request_id)
    master = get_master(request_id)
    if not current or not master:
        raise NotFoundError(f"Request {request_id} not found")

    provided_tracking_hash = hash_tracking_code(body["trackingCode"])
    if master.get("trackingCodeHash") != provided_tracking_hash:
        raise ForbiddenError("Invalid tracking code")

    if RequestStatus.is_terminal(RequestStatus(current["status"])):
        raise ConflictError("Cannot update a request in terminal state")

    update_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    update_item = {
        "PK": f"REQ#{request_id}",
        "SK": f"UPDATE#{now}#{update_id}",
        "itemType": "CITIZEN_UPDATE",
        "updateId": update_id,
        "requestId": request_id,
        "updateType": update_type.value,
        "updatePayload": body["updatePayload"],
        "citizenAuthMethod": "tracking_code",
        "citizenPhoneHash": citizen_phone_hash,
        "trackingCodeHash": tracking_code_hash or provided_tracking_hash,
        "clientIp": client_ip,
        "userAgent": user_agent,
        "createdAt": now,
    }

    try:
        put_citizen_update(update_item)
        update_master_fields(request_id, {"lastCitizenUpdateAt": now})
    except Exception as e:
        if idempotency_key:
            finalize_failure(idempotency_key, "UPDATE_FAILED", str(e))
        raise

    result = {
        "updateId": update_id,
        "requestId": request_id,
        "updateType": update_type.value,
        "createdAt": now,
    }

    if idempotency_key:
        finalize_success(
            idempotency_key=idempotency_key,
            response_status_code=201,
            response_body=json.dumps(result),
        )

    try:
        publish_citizen_updated(
            request_id=request_id,
            update_id=update_id,
            update_type=update_type.value,
            update_payload=body["updatePayload"],
            created_at=now,
        )
    except Exception:
        logger.exception("Failed to publish citizen-updated event")

    return result


def _validate_update_payload(update_type: UpdateType, payload: Any) -> list[dict[str, str]]:
    if not isinstance(payload, dict):
        return [{"field": "updatePayload", "issue": "must be an object"}]

    errors: list[dict[str, str]] = []
    if update_type == UpdateType.NOTE:
        if not _non_empty_string(payload.get("note")):
            errors.append({"field": "updatePayload.note", "issue": "is required and must be a non-empty string"})
    elif update_type == UpdateType.LOCATION_DETAILS:
        if not _non_empty_string(payload.get("locationDetails")):
            errors.append({"field": "updatePayload.locationDetails", "issue": "is required and must be a non-empty string"})
    elif update_type == UpdateType.PEOPLE_COUNT:
        people_count = payload.get("peopleCount")
        if not isinstance(people_count, int) or people_count < 1:
            errors.append({"field": "updatePayload.peopleCount", "issue": "must be an integer greater than 0"})
    elif update_type == UpdateType.SPECIAL_NEEDS:
        if not _non_empty_string(payload.get("specialNeeds")):
            errors.append({"field": "updatePayload.specialNeeds", "issue": "is required and must be a non-empty string"})
    elif update_type == UpdateType.CONTACT_INFO:
        if not _non_empty_string(payload.get("contactPhone")) and not _non_empty_string(payload.get("contactName")):
            errors.append({
                "field": "updatePayload",
                "issue": "at least one of contactPhone/contactName is required for CONTACT_INFO",
            })
        if _non_empty_string(payload.get("contactPhone")):
            for phone_error in validate_phone(payload["contactPhone"]):
                errors.append({"field": "updatePayload.contactPhone", "issue": phone_error["issue"]})

    return errors


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
