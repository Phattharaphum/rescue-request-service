from src.application.services.event_publisher import publish_status_changed
from src.application.services.idempotency_service import check_and_reserve, finalize_failure, finalize_success
from src.application.services.state_transition_service import execute_transition
from src.domain.enums.request_status import RequestStatus
from src.handlers.handler_utils import cors_handler, get_header, handle_error, parse_body, require_uuid_path_param
from src.shared.response import ok
from src.shared.validators import parse_optional_int
import json


@cors_handler
def handler(event, context):
    try:
        request_id = require_uuid_path_param(event, "requestId")
        body = parse_body(event)
        idempotency_key = get_header(event, "X-Idempotency-Key")
        if_match = get_header(event, "If-Match")
        expected_version = parse_optional_int(if_match, "If-Match", minimum=1)
        idempotency_reservation: dict | None = None

        if idempotency_key:
            idempotency_reservation = check_and_reserve(
                idempotency_key=idempotency_key,
                operation_name="Assign",
                resource_scope=f"POST:/v1/rescue-requests/{request_id}/assign",
                request_body=body,
            )
            if idempotency_reservation and idempotency_reservation.get("replay"):
                return ok(json.loads(idempotency_reservation["body"]), event)

        try:
            result = execute_transition(
                request_id=request_id,
                new_status=RequestStatus.ASSIGNED,
                changed_by=body.get("changedBy", "staff"),
                changed_by_role=body.get("changedByRole", "staff"),
                payload=body,
                expected_version=expected_version,
            )
        except Exception as e:
            if idempotency_key:
                finalize_failure(
                    idempotency_key=idempotency_key,
                    error_code="ASSIGN_FAILED",
                    error_message=str(e),
                    idempotency_key_hash=idempotency_reservation.get("keyHash") if idempotency_reservation else None,
                    lock_owner=idempotency_reservation.get("lockOwner") if idempotency_reservation else None,
                )
            raise

        if idempotency_key:
            finalize_success(
                idempotency_key=idempotency_key,
                response_status_code=200,
                response_body=json.dumps(result, default=str),
                idempotency_key_hash=idempotency_reservation.get("keyHash") if idempotency_reservation else None,
                lock_owner=idempotency_reservation.get("lockOwner") if idempotency_reservation else None,
            )

        try:
            publish_status_changed(
                request_id, result["previousStatus"], result["newStatus"], result["eventId"], result["version"]
            )
        except Exception:
            pass

        return ok(result, event)
    except Exception as e:
        return handle_error(e, event)
