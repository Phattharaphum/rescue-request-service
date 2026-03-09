import json
import uuid
from datetime import datetime, timezone

from src.adapters.persistence.rescue_request_repository import (
    get_current_state,
    put_citizen_update,
    update_master_fields,
)
from src.application.services.event_publisher import publish_citizen_updated
from src.application.services.idempotency_service import check_and_reserve, finalize_failure, finalize_success
from src.domain.enums.update_type import UpdateType
from src.domain.enums.request_status import RequestStatus
from src.shared.errors import ConflictError, ValidationError
from src.shared.logger import get_logger
from src.shared.validators import validate_required_fields

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
    errors = validate_required_fields(body, ["updateType", "updatePayload"])
    if errors:
        raise ValidationError("Input validation failed", errors)

    try:
        UpdateType(body["updateType"])
    except ValueError:
        raise ValidationError(
            f"Invalid updateType: {body['updateType']}",
            [{"field": "updateType", "issue": f"must be one of: {', '.join(t.value for t in UpdateType)}"}],
        )

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
    if not current:
        from src.shared.errors import NotFoundError
        raise NotFoundError(f"Request {request_id} not found")

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
        "updateType": body["updateType"],
        "updatePayload": body["updatePayload"],
        "citizenAuthMethod": "tracking_code",
        "citizenPhoneHash": citizen_phone_hash,
        "trackingCodeHash": tracking_code_hash,
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
        "updateType": body["updateType"],
        "createdAt": now,
    }

    if idempotency_key:
        finalize_success(
            idempotency_key=idempotency_key,
            response_status_code=201,
            response_body=json.dumps(result),
        )

    try:
        publish_citizen_updated(request_id=request_id, update_id=update_id, update_type=body["updateType"])
    except Exception:
        logger.exception("Failed to publish citizen-updated event")

    return result
