from src.adapters.persistence.rescue_request_repository import list_by_incident
from src.shared.logger import get_logger

logger = get_logger(__name__)


def execute(incident_id: str, limit: int = 20, cursor: str | None = None, status: str | None = None) -> dict:
    result = list_by_incident(incident_id, limit=limit, cursor=cursor, status=status)
    items = []
    for item in result["items"]:
        cleaned = {k: v for k, v in item.items() if k not in {"PK", "SK", "itemType"}}
        items.append(cleaned)
    return {
        "items": items,
        "nextCursor": result.get("nextCursor"),
    }
