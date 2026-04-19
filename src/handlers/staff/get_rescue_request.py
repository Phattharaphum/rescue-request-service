from src.application.usecases import get_rescue_request
from src.handlers.handler_utils import cors_handler, get_query_param, handle_error, require_uuid_path_param
from src.shared.response import ok


@cors_handler
def handler(event, context):
    try:
        request_id = require_uuid_path_param(event, "requestId")
        include_events = get_query_param(event, "includeEvents", "false").lower() == "true"
        include_updates = get_query_param(event, "includeCitizenUpdates", "false").lower() == "true"

        result = get_rescue_request.execute(
            request_id=request_id,
            include_events=include_events,
            include_citizen_updates=include_updates,
        )
        return ok(result, event)
    except Exception as e:
        return handle_error(e, event)

