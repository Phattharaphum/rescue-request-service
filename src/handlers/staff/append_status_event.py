from src.application.usecases import append_status_event
from src.handlers.handler_utils import get_header, get_path_param, handle_error, parse_body
from src.shared.response import ok


def handler(event, context):
    try:
        request_id = get_path_param(event, "requestId")
        body = parse_body(event)
        idempotency_key = get_header(event, "X-Idempotency-Key")
        if_match = get_header(event, "If-Match")
        expected_version = int(if_match) if if_match else None

        result = append_status_event.execute(
            request_id=request_id,
            body=body,
            idempotency_key=idempotency_key,
            expected_version=expected_version,
        )
        return ok(result)
    except Exception as e:
        return handle_error(e)
