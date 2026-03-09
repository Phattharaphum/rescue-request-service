from src.adapters.persistence.rescue_request_repository import list_citizen_updates
from src.shared.logger import get_logger

logger = get_logger(__name__)


def execute(request_id: str, limit: int = 20, cursor: str | None = None, since: str | None = None) -> dict:
    result = list_citizen_updates(request_id, limit=limit, cursor=cursor, since=since)
    items = []
    for item in result["items"]:
        cleaned = {k: v for k, v in item.items() if k not in {"PK", "SK", "itemType"}}
        items.append(cleaned)
    return {
        "items": items,
        "nextCursor": result.get("nextCursor"),
    }
