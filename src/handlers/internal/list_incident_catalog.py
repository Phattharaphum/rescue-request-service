from src.application.usecases import list_internal_incident_catalog
from src.handlers.handler_utils import cors_handler, handle_error
from src.shared.response import ok


@cors_handler
def handler(event, context):
    try:
        result = list_internal_incident_catalog.execute()
        return ok(result, event)
    except Exception as exc:
        return handle_error(exc, event)
