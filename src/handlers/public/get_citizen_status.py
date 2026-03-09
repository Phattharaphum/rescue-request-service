from src.application.usecases import get_citizen_status
from src.handlers.handler_utils import get_path_param, handle_error
from src.shared.response import ok


def handler(event, context):
    try:
        request_id = get_path_param(event, "requestId")
        result = get_citizen_status.execute(request_id=request_id)
        return ok(result)
    except Exception as e:
        return handle_error(e)
