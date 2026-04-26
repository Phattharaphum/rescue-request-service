from typing import Callable

from src.adapters.auth.internal_api_key import require_internal_api_key
from src.application.usecases import internal_maintenance
from src.handlers.handler_utils import cors_handler, get_header, handle_error
from src.shared.errors import BadRequestError
from src.shared.response import ok


@cors_handler
def handler(event, context):
    try:
        require_internal_api_key(get_header(event, "api-key"))
        operation = _resolve_operation(event)
        return ok(operation(), event)
    except Exception as exc:
        return handle_error(exc, event)


def _resolve_operation(event: dict) -> Callable[[], dict]:
    method = str(event.get("httpMethod") or (event.get("requestContext") or {}).get("http", {}).get("method") or "")
    path = str(event.get("resource") or event.get("path") or (event.get("requestContext") or {}).get("path") or "")
    normalized_path = path.rstrip("/")

    if method.upper() != "DELETE":
        raise BadRequestError("Unsupported internal maintenance method")

    routes: dict[str, Callable[[], dict]] = {
        "/v1/internal/incidents/catalog": lambda: internal_maintenance.clear_incident_catalog(delete_requests=False),
        "/v1/internal/incidents/catalog/with-requests": lambda: internal_maintenance.clear_incident_catalog(
            delete_requests=True
        ),
        "/v1/internal/rescue-requests/orphaned": internal_maintenance.delete_orphaned_requests,
        "/v1/internal/rescue-requests": internal_maintenance.clear_requests,
        "/v1/internal/maintenance/all": internal_maintenance.clear_all_data,
    }
    operation = routes.get(normalized_path)
    if operation is None:
        raise BadRequestError("Unsupported internal maintenance route")
    return operation
