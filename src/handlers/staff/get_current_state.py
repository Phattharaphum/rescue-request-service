from src.application.usecases import get_current_state
from src.handlers.handler_utils import cors_handler, handle_error, require_uuid_path_param
from src.shared.response import ok


@cors_handler
def handler(event, context):
    try:
        request_id = require_uuid_path_param(event, "requestId")
        result = get_current_state.execute(request_id=request_id)
        return ok(result, event)
    except Exception as e:
        return handle_error(e, event)

