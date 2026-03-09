from src.adapters.persistence.rescue_request_repository import list_events
from src.shared.logger import get_logger

logger = get_logger(__name__)


def execute(request_id: str, limit: int = 20, cursor: str | None = None,
            since_version: int | None = None, order: str = "ASC") -> dict:
    result = list_events(request_id, limit=limit, cursor=cursor, since_version=since_version, order=order)
    items = []
    for item in result["items"]:
        cleaned = {k: v for k, v in item.items() if k not in {"PK", "SK", "itemType"}}
        items.append(cleaned)
    return {
        "items": items,
        "nextCursor": result.get("nextCursor"),
    }
