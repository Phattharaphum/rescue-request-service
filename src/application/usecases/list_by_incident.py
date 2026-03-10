from src.adapters.persistence.rescue_request_repository import get_current_state, get_master, list_by_incident
from src.shared.logger import get_logger

logger = get_logger(__name__)


def execute(incident_id: str, limit: int = 20, cursor: str | None = None, status: str | None = None) -> dict:
    result = list_by_incident(incident_id, limit=limit, cursor=cursor, status=status)
    items = []
    for incident_projection in result["items"]:
        cleaned_projection = _clean_item(incident_projection)
        request_id = cleaned_projection.get("requestId")

        master = _clean_item(get_master(request_id)) if request_id else {}
        current = _clean_item(get_current_state(request_id)) if request_id else {}
        latest_status = current.get("status") or cleaned_projection.get("status")

        if status and latest_status != status:
            continue

        detailed = dict(cleaned_projection)
        detailed.update(master)
        if latest_status is not None:
            detailed["status"] = latest_status
        detailed["currentState"] = current if current else None
        items.append(detailed)

    return {
        "items": items,
        "nextCursor": result.get("nextCursor"),
    }


def _clean_item(item: dict | None) -> dict:
    if not item:
        return {}
    return {k: v for k, v in item.items() if k not in {"PK", "SK", "itemType"}}
