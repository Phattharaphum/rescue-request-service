from src.application.usecases import list_by_incident
from src.handlers.handler_utils import get_path_param, get_query_param, handle_error
from src.shared.response import ok
from src.shared.validators import validate_pagination


def handler(event, context):
    try:
        incident_id = get_path_param(event, "incidentId")
        limit, cursor = validate_pagination(
            get_query_param(event, "limit"),
            get_query_param(event, "cursor"),
        )
        status = get_query_param(event, "status")

        result = list_by_incident.execute(
            incident_id=incident_id,
            limit=limit,
            cursor=cursor,
            status=status,
        )
        return ok(result)
    except Exception as e:
        return handle_error(e)
