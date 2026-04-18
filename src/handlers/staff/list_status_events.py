from src.application.usecases import list_status_events
from src.handlers.handler_utils import cors_handler, get_query_param, handle_error, require_uuid_path_param
from src.shared.errors import BadRequestError
from src.shared.response import ok
from src.shared.validators import parse_optional_int, validate_pagination


@cors_handler
def handler(event, context):
    try:
        request_id = require_uuid_path_param(event, "requestId")
        limit, cursor = validate_pagination(
            get_query_param(event, "limit"),
            get_query_param(event, "cursor"),
        )
        since_version = get_query_param(event, "sinceVersion")
        parsed_since_version = parse_optional_int(since_version, "sinceVersion", minimum=0)
        order = (get_query_param(event, "order", "ASC") or "ASC").upper()
        if order not in {"ASC", "DESC"}:
            raise BadRequestError(
                "order must be ASC or DESC",
                [{"field": "order", "issue": "must be ASC or DESC"}],
            )

        result = list_status_events.execute(
            request_id=request_id,
            limit=limit,
            cursor=cursor,
            since_version=parsed_since_version,
            order=order,
        )
        return ok(result, event)
    except Exception as e:
        return handle_error(e, event)

