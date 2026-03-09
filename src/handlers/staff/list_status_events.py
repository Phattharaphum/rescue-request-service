from src.application.usecases import list_status_events
from src.handlers.handler_utils import get_path_param, get_query_param, handle_error
from src.shared.response import ok
from src.shared.validators import validate_pagination


def handler(event, context):
    try:
        request_id = get_path_param(event, "requestId")
        limit, cursor = validate_pagination(
            get_query_param(event, "limit"),
            get_query_param(event, "cursor"),
        )
        since_version = get_query_param(event, "sinceVersion")
        order = get_query_param(event, "order", "ASC")

        result = list_status_events.execute(
            request_id=request_id,
            limit=limit,
            cursor=cursor,
            since_version=int(since_version) if since_version else None,
            order=order,
        )
        return ok(result)
    except Exception as e:
        return handle_error(e)
