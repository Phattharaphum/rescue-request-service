from src.application.services.event_publisher import publish_resolved, publish_status_changed
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

        if idempotency_key:
            replay = check_and_reserve(idempotency_key, "Resolve", body)
            if replay and replay.get("replay"):
                return ok(json.loads(replay["body"]), event)

        try:
            result = execute_transition(
                request_id=request_id,
                new_status=RequestStatus.RESOLVED,
                changed_by=body.get("changedBy", "staff"),
                changed_by_role=body.get("changedByRole", "staff"),
                payload=body,
                expected_version=expected_version,
            )
        except Exception as e:
            if idempotency_key:
                finalize_failure(idempotency_key, "RESOLVE_FAILED", str(e))
            raise

        if idempotency_key:
            finalize_success(idempotency_key, 200, json.dumps(result, default=str))

        try:
            publish_status_changed(request_id, result["previousStatus"], result["newStatus"], result["eventId"], result["version"])
            publish_resolved(request_id, result["eventId"])
        except Exception:
            pass

        return ok(result, event)
    except Exception as e:
        return handle_error(e, event)

