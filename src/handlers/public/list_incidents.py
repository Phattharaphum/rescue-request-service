from src.application.usecases import list_incidents
from src.handlers.handler_utils import cors_handler, get_query_param, handle_error
from src.shared.response import ok
from src.shared.validators import validate_pagination


@cors_handler
def handler(event, context):
    try:
        limit, cursor = validate_pagination(
            get_query_param(event, "limit"),
            get_query_param(event, "cursor"),
        )
        status = get_query_param(event, "status")
        result = list_incidents.execute(limit=limit, cursor=cursor, status=status)
        return ok(result)
    except Exception as exc:
        return handle_error(exc, event)
