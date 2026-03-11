from src.application.usecases import get_current_state
from src.handlers.handler_utils import cors_handler, get_path_param, handle_error
from src.shared.response import ok


@cors_handler
def handler(event, context):
    try:
        request_id = get_path_param(event, "requestId")
        result = get_current_state.execute(request_id=request_id)
        return ok(result)
    except Exception as e:
        return handle_error(e, event)

