from src.adapters.auth.internal_api_key import require_internal_api_key
from src.application.usecases import list_internal_incident_catalog
from src.handlers.handler_utils import cors_handler, get_header, handle_error
from src.shared.response import ok


@cors_handler
def handler(event, context):
    try:
        require_internal_api_key(get_header(event, "api-key"))
        result = list_internal_incident_catalog.execute()
        return ok(result, event)
    except Exception as exc:
        return handle_error(exc, event)
