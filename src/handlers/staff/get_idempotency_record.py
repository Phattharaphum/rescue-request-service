from src.application.usecases import get_idempotency_record
from src.handlers.handler_utils import cors_handler, get_path_param, get_query_param, handle_error
from src.shared.response import ok


@cors_handler
def handler(event, context):
    try:
        key_hash = get_path_param(event, "idempotencyKeyHash")
        include_response = get_query_param(event, "includeResponse", "false").lower() == "true"
        include_fingerprint = get_query_param(event, "includeRequestFingerprint", "false").lower() == "true"

        result = get_idempotency_record.execute(
            idempotency_key_hash=key_hash,
            include_response=include_response,
            include_fingerprint=include_fingerprint,
        )
        return ok(result)
    except Exception as e:
        return handle_error(e, event)

