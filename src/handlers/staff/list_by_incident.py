from src.application.usecases import list_by_incident
from src.domain.enums.request_status import RequestStatus
from src.handlers.handler_utils import cors_handler, get_query_param, handle_error, require_path_param
from src.shared.errors import BadRequestError
from src.shared.response import ok
from src.shared.validators import validate_pagination


@cors_handler
def handler(event, context):
    try:
        incident_id = require_path_param(event, "incidentId")
        limit, cursor = validate_pagination(
            get_query_param(event, "limit"),
            get_query_param(event, "cursor"),
        )
        status = get_query_param(event, "status")
        if status and status not in {item.value for item in RequestStatus}:
            raise BadRequestError(
                "status must be a valid RequestStatus",
                [{"field": "status", "issue": f"must be one of: {', '.join(item.value for item in RequestStatus)}"}],
            )

        result = list_by_incident.execute(
            incident_id=incident_id,
            limit=limit,
            cursor=cursor,
            status=status,
        )
        return ok(result, event)
    except Exception as e:
        return handle_error(e, event)

