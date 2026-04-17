import json

from src.adapters.persistence.rescue_request_repository import (
    get_current_state,
    get_master,
    update_current_fields,
    update_master_fields,
)
from src.application.services.event_publisher import publish_citizen_updated, publish_prioritization_re_evaluation
from src.application.services.idempotency_service import check_and_reserve, finalize_failure, finalize_success
from src.application.services.prioritization_contract import apply_patch_updates_to_master
from src.domain.enums.request_status import RequestStatus
from src.shared.errors import ConflictError, NotFoundError, ValidationError
from src.shared.logger import get_logger

logger = get_logger(__name__)

ALLOWED_FIELDS = {"description", "peopleCount", "specialNeeds", "locationDetails", "addressLine"}
FORBIDDEN_FIELDS = {"incidentId", "status", "requestId"}


def execute(request_id: str, body: dict, idempotency_key: str | None = None, expected_version: int | None = None) -> dict:
    if idempotency_key:
        replay = check_and_reserve(
            idempotency_key=idempotency_key,
            operation_name="PatchRescueRequest",
            request_body=body,
        )
        if replay and replay.get("replay"):
            return json.loads(replay["body"])

    forbidden_present = set(body.keys()) & FORBIDDEN_FIELDS
    if forbidden_present:
        raise ValidationError(
            f"Cannot modify fields: {', '.join(forbidden_present)}",
            [{"field": f, "issue": "modification not allowed"} for f in forbidden_present],
        )

    updates = {k: v for k, v in body.items() if k in ALLOWED_FIELDS}
    if not updates:
        raise ValidationError("No valid fields to update")

    current = get_current_state(request_id)
    master = get_master(request_id)
    if not current or not master:
        raise NotFoundError(f"Request {request_id} not found")

    if RequestStatus.is_terminal(RequestStatus(current["status"])):
        raise ConflictError("Cannot modify a request in terminal state")

    try:
        update_master_fields(request_id, updates, expected_version)
    except Exception as e:
        if idempotency_key:
            finalize_failure(idempotency_key, "PATCH_FAILED", str(e))
        raise

    result = {"requestId": request_id, "updated": list(updates.keys())}

    if idempotency_key:
        finalize_success(
            idempotency_key=idempotency_key,
            response_status_code=200,
            response_body=json.dumps(result),
        )

    try:
        publish_citizen_updated(
            request_id=request_id,
            update_id="patch",
            update_type="PATCH",
            update_payload=updates,
        )
    except Exception:
        logger.exception("Failed to publish citizen-updated event")

    try:
        updated_request = apply_patch_updates_to_master(master, updates)
        header = publish_prioritization_re_evaluation(
            request_data=updated_request,
            correlation_id=current.get("lastPrioritizationMessageId"),
        )
        if header:
            update_current_fields(
                request_id=request_id,
                updates={
                    "lastPrioritizationMessageId": header["messageId"],
                    "lastPrioritizationMessageType": header["messageType"],
                    "lastPrioritizationSentAt": header["sentAt"],
                },
            )
    except Exception:
        logger.exception("Failed to publish prioritization re-evaluation event")

    return result
