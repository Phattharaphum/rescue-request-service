from src.application.usecases import list_citizen_updates
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
        since = get_query_param(event, "since")

        result = list_citizen_updates.execute(
            request_id=request_id,
            limit=limit,
            cursor=cursor,
            since=since,
        )
        return ok(result)
    except Exception as e:
        return handle_error(e)
