from datetime import datetime

from src.adapters.persistence.rescue_request_repository import get_current_state, list_citizen_updates
from src.shared.errors import BadRequestError, NotFoundError
from src.shared.logger import get_logger

logger = get_logger(__name__)


def execute(request_id: str, limit: int = 20, cursor: str | None = None, since: str | None = None) -> dict:
    current = get_current_state(request_id)
    if not current:
        raise NotFoundError(f"Request {request_id} not found")

    normalized_since = _normalize_since_iso8601(since) if since else None

    result = list_citizen_updates(request_id, limit=limit, cursor=cursor, since=normalized_since)
    items = []
    for item in result["items"]:
        cleaned = _clean_item(item)
        items.append(cleaned)
    return {
        "items": items,
        "nextCursor": result.get("nextCursor"),
    }


def _clean_item(item: dict) -> dict:
    allowed_fields = {
        "updateId",
        "requestId",
        "updateType",
        "updatePayload",
        "citizenAuthMethod",
        "createdAt",
    }
    return {k: v for k, v in item.items() if k in allowed_fields}


def _normalize_since_iso8601(value: str) -> str:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        raise BadRequestError("since must be a valid ISO-8601 datetime")
