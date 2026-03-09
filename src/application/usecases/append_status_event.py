import json

from src.application.services.event_publisher import publish_cancelled, publish_resolved, publish_status_changed
from src.application.services.idempotency_service import check_and_reserve, finalize_failure, finalize_success
from src.application.services.state_transition_service import execute_transition
from src.domain.enums.request_status import RequestStatus
from src.shared.errors import ValidationError
from src.shared.logger import get_logger
from src.shared.validators import validate_required_fields

logger = get_logger(__name__)


def execute(
    request_id: str,
    body: dict,
    idempotency_key: str | None = None,
    expected_version: int | None = None,
) -> dict:
    errors = validate_required_fields(body, ["newStatus", "changedBy", "changedByRole"])
    if errors:
        raise ValidationError("Input validation failed", errors)

    try:
        new_status = RequestStatus(body["newStatus"])
    except ValueError:
        raise ValidationError(
            f"Invalid status: {body['newStatus']}",
            [{"field": "newStatus", "issue": f"must be one of: {', '.join(s.value for s in RequestStatus)}"}],
        )

    if idempotency_key:
        replay = check_and_reserve(
            idempotency_key=idempotency_key,
            operation_name="AppendStatusEvent",
            request_body=body,
        )
        if replay and replay.get("replay"):
            return json.loads(replay["body"])

    try:
        result = execute_transition(
            request_id=request_id,
            new_status=new_status,
            changed_by=body["changedBy"],
            changed_by_role=body["changedByRole"],
            payload=body,
            expected_version=expected_version,
        )
    except Exception as e:
        if idempotency_key:
            finalize_failure(idempotency_key, "TRANSITION_FAILED", str(e))
        raise

    if idempotency_key:
        finalize_success(
            idempotency_key=idempotency_key,
            response_status_code=200,
            response_body=json.dumps(result, default=str),
        )

    try:
        publish_status_changed(
            request_id=request_id,
            previous_status=result["previousStatus"],
            new_status=result["newStatus"],
            event_id=result["eventId"],
            version=result["version"],
            correlation_id=request_id,
        )
        if new_status == RequestStatus.RESOLVED:
            publish_resolved(request_id=request_id, event_id=result["eventId"])
        elif new_status == RequestStatus.CANCELLED:
            publish_cancelled(request_id=request_id, event_id=result["eventId"], reason=body.get("reason", ""))
    except Exception:
        logger.exception("Failed to publish status events")

    return result
