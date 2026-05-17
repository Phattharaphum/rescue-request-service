from src.application.usecases import list_incidents
from src.handlers.handler_utils import cors_handler, get_query_param, handle_error
from src.shared.response import ok


@cors_handler
def handler(event, context):
    try:
        status = get_query_param(event, "status")
        result = list_incidents.execute(status=status)
        return ok(result, event)
    except Exception as exc:
        return handle_error(exc, event)
