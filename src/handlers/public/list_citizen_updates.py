from src.application.usecases import list_citizen_updates
from src.handlers.handler_utils import cors_handler, get_query_param, handle_error, require_uuid_path_param
from src.shared.response import ok
from src.shared.validators import validate_pagination


@cors_handler
def handler(event, context):
    try:
        request_id = require_uuid_path_param(event, "requestId")
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
        return ok(result, event)
    except Exception as e:
        return handle_error(e, event)

