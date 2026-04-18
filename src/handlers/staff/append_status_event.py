from src.application.usecases import append_status_event
from src.handlers.handler_utils import cors_handler, get_header, handle_error, parse_body, require_uuid_path_param
from src.shared.response import ok
from src.shared.validators import parse_optional_int


@cors_handler
def handler(event, context):
    try:
        request_id = require_uuid_path_param(event, "requestId")
        body = parse_body(event)
        idempotency_key = get_header(event, "X-Idempotency-Key")
        if_match = get_header(event, "If-Match")
        expected_version = parse_optional_int(if_match, "If-Match", minimum=1)

        result = append_status_event.execute(
            request_id=request_id,
            body=body,
            idempotency_key=idempotency_key,
            expected_version=expected_version,
        )
        return ok(result, event)
    except Exception as e:
        return handle_error(e, event)

